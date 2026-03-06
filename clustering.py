from _utils import *
from materialization import materialize_dataset
import pandas as pd
from tslearn.clustering import TimeSeriesKMeans
from tslearn.utils import to_time_series_dataset

clusters_csv_path = get_data_filepath(f"clusters_%s.csv")

def read_list_as(list_string, cast_function) :
	return list(map(cast_function, list_string.strip("[]").split(",")))

def load_cohort_time_series(filepath, clustering_years=CLUSTERING_YEARS) :
	"""Load CSV and return dataframe and time_series_data (tslearn-compatible ndarray)."""
	input_csv_path = get_data_filepath(filepath)
	df = pd.read_csv(input_csv_path)
	values_matrix = df['valore'].apply(lambda x: read_list_as(x, float)).tolist()
	
	# Explode the values in 10 different columns
	values_df = pd.DataFrame(values_matrix, columns=[f'm{i+1}' for i in range(clustering_years)])
	df = pd.concat([df.drop(columns=['valore']), values_df], axis=1)
		
	# Saving start year
	if 'data' in df.columns :
		df['annoinizio'] = df['data'].apply(lambda x: read_list_as(x, int)[0])
		df.drop(['data'], axis=1, inplace=True)
	time_series_data = to_time_series_dataset(values_matrix)
	return df, time_series_data

def compute_clusters_for_cohort(k, cohort, max_iter=100, n_jobs=8, random_state=None) :
	logger.info(f"Computing { k } clusters for cohort: { cohort }")
	
	filepath = f"measurements_{ cohort }.csv"
	df, time_series_data = load_cohort_time_series(filepath)

	# Perform temporal k-means clustering
	model = TimeSeriesKMeans(n_clusters=k, metric='dtw', max_iter=max_iter, n_jobs=n_jobs, random_state=random_state)
	model.fit(time_series_data)

	df['cluster'] = model.predict(time_series_data)
	return df, model.inertia_

def compute_clusters() :
	for cohort in ['NC','CC'] :
		df, _ = compute_clusters_for_cohort(N_CLUSTERS, cohort)
		df.to_csv(clusters_csv_path % cohort, index=False)
		logger.info(f"Clustering results saved to: { clusters_csv_path % cohort }")
	
	logger.info("Done")

def materialize_clusters() :
	attribute2datatype = {
			'idcentro' : 'integer',
			'idana' : 'integer'
	}
	for i in range(CLUSTERING_YEARS) :
		attribute2datatype['m%d' % (i+1)] = 'float'
	attribute2datatype.update({
		'annoinizio' : 'integer',
		'cluster' : 'varchar(255)'
	})

	for cohort in ['CC', 'NC'] :
		materialize_dataset(
			csv_filepath=clusters_csv_path % cohort,
			table_name='clusters_' + cohort,
			attribute2datatype=attribute2datatype,
			csv_dtype={'annoinizio' : 'Int64'}
		)

if __name__ == '__main__':
	compute_clusters()
	materialize_clusters()