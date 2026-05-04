from _utils import *
from clustering import load_cohort_time_series
import os
import json
import numpy as np
from tslearn.clustering import TimeSeriesKMeans
from tslearn.metrics import dtw
from scipy.optimize import linear_sum_assignment
from joblib import Parallel, delayed
from datetime import datetime

# Configuration
N_INIT_RUNS = 5
MAX_ITER = 100
PARALLEL_JOBS = -1
OUT_FOLDER = "stability_across_cohorts_results"
COHORTS = ['NC','CC']
RANDOM_SEED = 42
CLUSTERING_YEARS_1 = 10
CLUSTERING_YEARS_2 = 10
OTHER_SUFFIX = "10b3"

def run_single_kmeans(time_series_data, k, max_iter, seed, n_jobs, filename_template=None) :
	load_and_store = not (filename_template is None)
	
	if load_and_store :
		labels_file = filename_template % ("clusters", seed)
		centers_file = filename_template % ("centers", seed)

	if load_and_store and os.path.exists(labels_file) and os.path.exists(centers_file):
		# Import
		labels = np.load(labels_file)
		centers = np.load(centers_file)
	else :
		# Run k-means
		model = TimeSeriesKMeans(n_clusters=k, metric='dtw', max_iter=max_iter, n_jobs=n_jobs, random_state=seed)
		model.fit(time_series_data)
		labels = model.labels_.astype(np.int32)
		centers = model.cluster_centers_.copy()

		# Export
		if load_and_store :
			np.save(labels_file, labels)
			np.save(centers_file, centers)
	return labels, centers

def run_multiple_inits_parallel(filename_template, time_series_data, k, n_inits=N_INIT_RUNS, max_iter=MAX_ITER, n_jobs_tslearn=8, parallel_jobs=PARALLEL_JOBS, seeds=None) :
	"""Executes n_inits runs in parallel (joblib).
	   Reutnrs labels_all (n_inits x n_samples), centers_list, seeds_used."""
	if seeds is None :
		seeds = [int(RANDOM_SEED + i) for i in range(n_inits)]
	else :
		n_inits = len(seeds)

	logger.info(f"Staring {n_inits} parallel runs (k={k}) ...")
	results = Parallel(
		n_jobs=parallel_jobs
		, backend="threading" # (for Windows execution)
	)(
		delayed(run_single_kmeans)(time_series_data, k, max_iter, s, n_jobs_tslearn, filename_template) for s in seeds
	)
	labels_all = np.stack([r[0] for r in results], axis=0)	   # shape (n_runs, n_samples)
	centers_list = [r[1] for r in results]
	return labels_all, centers_list, seeds

def intersect_cohorts(time_series_data1, labels_all1, time_series_data2, labels_all2, df1, df2) :
	df1 = df1.reset_index(drop=True)
	df2 = df2.reset_index(drop=True)

	# Use explicit composite key for intersection
	key_cols = ['idcentro', 'idana']

	# Cast to string to avoid type issues
	ids1 = df1[key_cols].astype(str).agg('-'.join, axis=1)
	ids2 = df2[key_cols].astype(str).agg('-'.join, axis=1)
	mask1 = ids1.isin(set(ids2.values))
	mask2 = ids2.isin(set(ids1.values))
	intersect_idx1 = np.where(mask1)[0]
	intersect_idx2 = np.where(mask2)[0]

	time_series_data1 = time_series_data1[intersect_idx1]
	time_series_data2 = time_series_data2[intersect_idx2]

	if intersect_idx1.size == 0 or intersect_idx2.size == 0:
		logger.warning("No overlap found between cohorts.")
		labels_all1 = labels_all1[:, []]
		labels_all2 = labels_all2[:, []]
	else:
		labels_all1 = labels_all1[:, intersect_idx1]
		labels_all2 = labels_all2[:, intersect_idx2]

	return time_series_data1, labels_all1, time_series_data2, labels_all2

def compute_contingency(labels_ref, labels_other, k) :
	"""Returns k x k matrix with counts between labels_ref and labels_other."""
	cont = np.zeros((k, k), dtype=int)
	for i in range(k) :
		for j in range(k) :
			cont[i, j] = np.sum((labels_ref == i) & (labels_other == j))
	return cont

def best_label_mapping_from_contingency(labels_to_rearrange, labels_ref, k) :
	"""Computes the best-match map between label_other -> label_ref using contingency map."""
	cont = compute_contingency(labels_ref, labels_to_rearrange, k)
	# maximize overlap -> minimize -cont
	cost = -cont
	row_ind, col_ind = linear_sum_assignment(cost)
	# row_ind are reference labels, col_ind are other labels, so mapping other->ref:
	mapping = {int(col): int(row) for row, col in zip(row_ind, col_ind)}
	# apply mapping (for labels outside 0..k-1 you might want to handle separately)
	return np.vectorize(lambda x: mapping.get(int(x), -1))(labels_to_rearrange)

def best_label_mapping_from_centroids(labels_to_rearrange, centers, centers_ref, k) :
	"""Computes the best-match map between label_other -> label_ref using centroids."""
	cost = np.zeros((k, k))
	for i in range(k):
		for j in range(k):
			cost[i, j] = dtw(
				centers_ref[i].ravel(),
				centers[j].ravel()
			)
	row_ind, col_ind = linear_sum_assignment(cost)
	# row_ind are reference labels, col_ind are other labels, so mapping other->ref:
	mapping = {int(col): int(row) for row, col in zip(row_ind, col_ind)}
	# apply mapping (for labels outside 0..k-1 you might want to handle separately)
	return np.vectorize(lambda x: mapping.get(int(x), -1))(labels_to_rearrange)

def cluster_reproducibility(labels1, labels2, k) :
    """
    Returns percentages of cohort1 patients assigned to the same cluster in labels2.
        per_cluster_pct_same: list of length k (percent of cohort1 patients in each cluster matched)
        global_pct_same: float (percent of all cohort1 patients matched correctly)
    """
    per_cluster_pct_same = []
    total_same = 0
    total_patients = len(labels1)

    for c in range(k):
        idx1 = np.where(labels1 == c)[0]
        idx2 = np.where(labels2 == c)[0]

        set1, set2 = set(idx1), set(idx2)
        if len(idx1) == 0:
            per_cluster_pct_same.append(0.0)
        else:
            per_cluster_pct_same.append(len(set1 & set2) / len(set1))

        total_same += len(set1 & set2)
    global_pct_same = total_same / total_patients if total_patients > 0 else 0.0

    return per_cluster_pct_same, global_pct_same

def run_stability_for_cohort(cohort, other_suffix, k, n_inits=N_INIT_RUNS, max_iter=MAX_ITER, n_jobs_tslearn=8, parallel_jobs=PARALLEL_JOBS, out_folder=OUT_FOLDER) :
	os.makedirs(out_folder, exist_ok=True)
	t0 = datetime.now()
	logger.info(f"=== START cohort={cohort} k={k} ===")

	df, time_series_data = load_cohort_time_series(f"measurements_{ cohort }.csv", CLUSTERING_YEARS_1)
	n_samples = time_series_data.shape[0]
	logger.info(f"Loaded cohort {cohort}/10: n_samples={n_samples}, series length={time_series_data.shape[1]}")
	
	df2, time_series_data2 = load_cohort_time_series(f"measurements_{ cohort }_{ other_suffix }.csv", CLUSTERING_YEARS_2)
	n_samples2 = time_series_data.shape[0]
	logger.info(f"Loaded cohort {cohort}/{other_suffix}: n_samples={n_samples2}, series length={time_series_data2.shape[1]}")

	# 1) multiple parallel runs on the entire dataset
	labels_all, centers_list, seeds = run_multiple_inits_parallel(
		f"{ out_folder }/%s_{ cohort }_10_%s.npy",
		time_series_data, k, n_inits=n_inits, max_iter=max_iter, n_jobs_tslearn=n_jobs_tslearn, parallel_jobs=parallel_jobs
	)
	labels_all2, centers_list2, seeds2 = run_multiple_inits_parallel(
		f"{ out_folder }/%s_{ cohort }_{ other_suffix }_%s.npy",
		time_series_data2, k, n_inits=n_inits, max_iter=max_iter, n_jobs_tslearn=n_jobs_tslearn, parallel_jobs=parallel_jobs
	)
	time_series_data, labels_all, time_series_data2, labels_all2 = intersect_cohorts(time_series_data, labels_all, time_series_data2, labels_all2, df, df2)

	# 2) cluster reproducibility for each run
	k_val = centers_list[0].shape[0]
	n_runs = labels_all.shape[0]
	cluster_reprods = np.zeros((n_runs, k_val))
	cluster_reprods_global = np.zeros(n_runs)
	sums1a = np.zeros((k_val, time_series_data.shape[1]))
	sums1b = np.zeros((k_val, time_series_data.shape[1]))
	sums2a = np.zeros((k_val, time_series_data2.shape[1]))
	sums2b = np.zeros((k_val, time_series_data2.shape[1]))
	reference_labels = None
	reference_centers = None
	for r in range(n_runs) :
		labels1 = labels_all[r]
		labels2 = labels_all2[r]
		centers1 = centers_list[r]
		centers2 = centers_list2[r]

		if reference_labels is None :
			reference_labels = labels1
			reference_centers = centers1
		
		labels1a = best_label_mapping_from_contingency(labels1, reference_labels, k_val)
		labels2a = best_label_mapping_from_contingency(labels2, reference_labels, k_val)
		labels1b = best_label_mapping_from_centroids(labels1, centers1, reference_centers, k_val)
		labels2b = best_label_mapping_from_centroids(labels2, centers2, reference_centers, k_val)
		cluster_reprods[r, :], cluster_reprods_global[r] = cluster_reproducibility(labels1a, labels2a, k_val)
		
		# accumulate values per cluster
		for cluster_id in range(k_val):
			sums1a[cluster_id] += time_series_data [labels1a == cluster_id].mean(axis=0).flatten()
			sums1b[cluster_id] += time_series_data [labels1b == cluster_id].mean(axis=0).flatten()
			sums2a[cluster_id] += time_series_data2[labels2a == cluster_id].mean(axis=0).flatten()
			sums2b[cluster_id] += time_series_data2[labels2b == cluster_id].mean(axis=0).flatten()
		
	# stats per cluster
	cluster_reprods_mean = cluster_reprods.mean(axis=0).tolist()
	cluster_reprods_std = cluster_reprods.std(axis=0).tolist()
	cluster_reprods_global_mean = cluster_reprods_global.mean().tolist()
	cluster_reprods_global_std = cluster_reprods_global.std().tolist()

	# manually check mean of means of time series data
	# to map the cluster index to the right label
	logger.info(sums1a / n_runs)
	logger.info(sums1b / n_runs)
	logger.info(sums2a / n_runs)
	logger.info(sums2b / n_runs)

	# 4) saving reports and artifacts
	summary = {
		'cohort': cohort,
		'k': k,
		'n_samples': int(n_samples),
		'n_runs': int(n_runs),
		'seeds': seeds,
		'cluster_reproducibility_mean': cluster_reprods_mean,
		'cluster_reproducibility_std': cluster_reprods_std,
		'cluster_reproducibility_global_mean': cluster_reprods_global_mean,
		'cluster_reproducibility_global_std': cluster_reprods_global_std,
		'run_time_seconds': (datetime.now() - t0).total_seconds()
	}
	summary_fname = os.path.join(out_folder, f"stability_summary_{cohort}_k{k}_10_{other_suffix}.json")
	with open(summary_fname, 'w') as f :
		json.dump(summary, f, indent=2)
	logger.info(f"Saved summary to: {summary_fname}")
	
	logger.info(f"=== DONE cohort={cohort} k={k} (elapsed {(datetime.now()-t0).total_seconds():.0f}s) ===")
	return summary

if __name__ == "__main__" :
	K = N_CLUSTERS if 'N_CLUSTERS' in globals() else 4
	os.makedirs(OUT_FOLDER, exist_ok=True)

	for cohort in COHORTS :
		try :
			summary = run_stability_for_cohort(
				cohort, OTHER_SUFFIX,
				k=K,
				n_inits=N_INIT_RUNS,
				max_iter=MAX_ITER,
				n_jobs_tslearn=8,
				parallel_jobs=PARALLEL_JOBS,
				out_folder=OUT_FOLDER
			)
		except Exception as e :
			logger.exception(f"Error on cohort {cohort}: {e}")