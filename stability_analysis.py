from _utils import *
from clustering import load_cohort_time_series
import os
import json
import numpy as np
from tslearn.clustering import TimeSeriesKMeans
from scipy.optimize import linear_sum_assignment
from joblib import Parallel, delayed
from datetime import datetime

# Configuration
N_INIT_RUNS = 50
MAX_ITER = 100
PARALLEL_JOBS = -1
OUT_FOLDER = "stability_results"
COHORTS = ['NC', 'CC']
RANDOM_SEED = 42

def run_single_kmeans(time_series_data, k, max_iter, seed, n_jobs) :
	"""Executes a single fit (returning labels, centers, inertia)."""
	model = TimeSeriesKMeans(n_clusters=k, metric='dtw', max_iter=max_iter, n_jobs=n_jobs, random_state=seed)
	model.fit(time_series_data)
	labels = model.labels_.astype(np.int32)
	centers = model.cluster_centers_.copy()  # array (k, L, dim)
	inertia = getattr(model, "inertia_", None)
	return labels, centers, inertia

def run_multiple_inits_parallel(time_series_data, k, n_inits=N_INIT_RUNS, max_iter=MAX_ITER, n_jobs_tslearn=8, parallel_jobs=PARALLEL_JOBS, seeds=None) :
	"""Executes n_inits runs in parallel (joblib).
	   Reutnrs labels_all (n_inits x n_samples), centers_list, inertias, seeds_used."""
	if seeds is None :
		seeds = [int(RANDOM_SEED + i) for i in range(n_inits)]
	else :
		n_inits = len(seeds)

	logger.info(f"Staring {n_inits} parallel runs (k={k}) ...")
	results = Parallel(n_jobs=parallel_jobs)(
		delayed(run_single_kmeans)(time_series_data, k, max_iter, s, n_jobs_tslearn) for s in seeds
	)
	labels_all = np.stack([r[0] for r in results], axis=0)	   # shape (n_runs, n_samples)
	centers_list = [r[1] for r in results]
	inertias = [r[2] for r in results]
	return labels_all, centers_list, inertias, seeds

def compute_contingency(labels_ref, labels_other, k) :
	"""Returns k x k matrix with counts between labels_ref and labels_other."""
	cont = np.zeros((k, k), dtype=int)
	for i in range(k) :
		for j in range(k) :
			cont[i, j] = np.sum((labels_ref == i) & (labels_other == j))
	return cont

def best_label_mapping_from_contingency(labels_ref, labels_other, k) :
	"""Computes the best-match map between label_other -> label_ref using contingency map.
	   Return dict {old_label_in_other: matched_label_in_ref} and permutated labels_other_mapped."""
	cont = compute_contingency(labels_ref, labels_other, k)
	# maximize overlap -> minimize -cont
	cost = -cont
	row_ind, col_ind = linear_sum_assignment(cost)
	# row_ind are reference labels, col_ind are other labels, so mapping other->ref:
	mapping = {int(col): int(row) for row, col in zip(row_ind, col_ind)}
	# apply mapping (for labels outside 0..k-1 you might want to handle separately)
	labels_other_mapped = np.vectorize(lambda x: mapping.get(int(x), -1))(labels_other)
	return mapping, labels_other_mapped

def cluster_jaccard_with_mapping(labels_ref, labels_other, k) :
	"""Returns Jaccards per cluster after having alined labels_other on labels_ref."""
	mapping, labels_other_mapped = best_label_mapping_from_contingency(labels_ref, labels_other, k)
	scores = []
	for c in range(k) :
		A = set(np.where(labels_ref == c)[0])
		B = set(np.where(labels_other_mapped == c)[0])
		if len(A | B) == 0 :
			scores.append(1.0)
		else :
			scores.append(len(A & B) / len(A | B))
	return scores

def run_stability_for_cohort(cohort, k, n_inits=N_INIT_RUNS, max_iter=MAX_ITER, n_jobs_tslearn=8, parallel_jobs=PARALLEL_JOBS, out_folder=OUT_FOLDER) :
	os.makedirs(out_folder, exist_ok=True)
	t0 = datetime.now()
	logger.info(f"=== START cohort={cohort} k={k} ===")

	df_meta, time_series_data = load_cohort_time_series(cohort)
	n_samples = time_series_data.shape[0]
	logger.info(f"Loaded cohort {cohort}: n_samples={n_samples}, series length={time_series_data.shape[1]}")

	# 1) multiple parallel runs on the entire dataset
	labels_all, centers_list, inertias, seeds = run_multiple_inits_parallel(
		time_series_data, k, n_inits=n_inits, max_iter=max_iter, n_jobs_tslearn=n_jobs_tslearn, parallel_jobs=parallel_jobs
	)
	n_runs = labels_all.shape[0]

	# 2) cluster-level Jaccard (vs run 0) for each run
	k_val = centers_list[0].shape[0]
	cluster_jaccards = np.zeros((n_runs, k_val))
	labels_ref = labels_all[0]
	for r in range(n_runs) :
		cluster_jaccards[r, :] = cluster_jaccard_with_mapping(labels_ref, labels_all[r], k_val)
	# stats per cluster
	cluster_jaccard_mean = cluster_jaccards.mean(axis=0).tolist()
	cluster_jaccard_std = cluster_jaccards.std(axis=0).tolist()

	# 3) saving reports and artifacts
	summary = {
		'cohort': cohort,
		'k': k,
		'n_samples': int(n_samples),
		'n_runs': int(n_runs),
		'seeds': seeds,
		'inertias': [None if x is None else float(x) for x in inertias],
		'cluster_jaccard_mean_per_cluster': cluster_jaccard_mean,
		'cluster_jaccard_std_per_cluster': cluster_jaccard_std,
		'run_time_seconds': (datetime.now() - t0).total_seconds()
	}
	summary_fname = os.path.join(out_folder, f"stability_summary_{cohort}_k{k}.json")
	with open(summary_fname, 'w') as f :
		json.dump(summary, f, indent=2)
	logger.info(f"Saved summary to: {summary_fname}")

	# saving reference labels (run 0) in CSV (metadati + cluster)
	df_out = df_meta.copy()
	df_out['cluster_ref'] = labels_ref
	df_out.to_csv(os.path.join(out_folder, f"labels_ref_{cohort}_k{k}.csv"), index=False)
	# saving all labels (compressed .npz)
	np.savez_compressed(os.path.join(out_folder, f"labels_all_{cohort}_k{k}.npz"), labels_all=labels_all)

	logger.info(f"=== DONE cohort={cohort} k={k} (elapsed {(datetime.now()-t0).total_seconds():.0f}s) ===")
	return summary

if __name__ == "__main__" :
	K = N_CLUSTERS if 'N_CLUSTERS' in globals() else 4
	os.makedirs(OUT_FOLDER, exist_ok=True)

	for cohort in COHORTS :
		try :
			summary = run_stability_for_cohort(
				cohort,
				k=K,
				n_inits=N_INIT_RUNS,
				max_iter=MAX_ITER,
				n_jobs_tslearn=8,
				parallel_jobs=PARALLEL_JOBS,
				out_folder=OUT_FOLDER
			)
		except Exception as e :
			logger.exception(f"Error on cohort {cohort}: {e}")