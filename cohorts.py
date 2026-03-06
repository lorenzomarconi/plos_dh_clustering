from _utils import *
from pathlib import Path
import numpy as np
import pandas as pd
import os

NEODIAGNOSIS_YEARS = 5
SEQ_NUM_YEARS = CLUSTERING_YEARS
SEQ_MIN_SIZE = 10
MAX_CONSECUTIVE_DAYS = 365
FIRST_YEAR = 2006
LAST_YEAR = 2019
PATIENT_KEY = ["idcentro", "idana"]

def read_file_or_query(filename=None, query=None, dtype={}, force_query=False) :
	"""
	If a file name is specified and the file exists, then the dataframe is read from the CSV file.
	Otherwise, it runs the specified SQL query and returns the results as a dataframe.
	If the query has been executed and a file name is specified, the result of the query is saved in CSV format.

	Args:
		filename (str): the file name.
		query (str): a query for the database. If none is specified, the table name is used.
		dtype (dict): a dictionary for forcing the datatypes for columns (e.g. "{'col1' : 'Int64'}") wriiten to/read from the CSV file.
		force_query (bool): a Boolean for forcing the query to be executed even if the file exists.

	Returns:
		bool: The valid subsequence exists, None otherwise.
	"""
	filepath = get_data_filepath(filename)
	if not force_query and os.path.exists(filepath) :
		df = pd.read_csv(filepath, dtype=dtype)
	else :
		df = pd.read_sql(query, db_engine)
		for col_name, col_type in dtype.items() :
			# Force columns typing
			df[col_name] = np.where(df[col_name].notnull(), df[col_name].astype(col_type), df[col_name])
		
		path = Path(filepath)
		path.parent.mkdir(parents=True, exist_ok=True)
		df.to_csv(path, index=False)
	return df

def find_valid_subsequence(
		dates,
		seq_min_size=SEQ_MIN_SIZE,
		seq_num_years=SEQ_NUM_YEARS,
		max_consecutive_days=MAX_CONSECUTIVE_DAYS
	) :
	"""
	Takes a sequence of dates and checks whether there exists a valid subsequence.
	By default, a valid subsequence should:
	- have at least 10 entries
	- span over at least of 10 years (e.g. 01/01/2006-31/12/2015, but also 30/10/2006-05/03/2015 would be ok)
	- have at most one year (365 days) between two consecutive entries

	Args:
		dates: The sequence of dates.
		seq_min_size (int): the minimum number of allowed dates for the sequence.
		seq_num_years (int): the number of solar years over which the subsequence should span.
		max_consecutive_days (int): the maximum number of consecutive days allowed between two dates.

	Returns:
		tuple or None:
			- None: If no subsequence exists.
			- tuple: A pair of values otherwise:
				- int: The start index of the subsequence.
				- int: The end index of the subsequence.
	"""
	num_dates = len(dates)
	days_distance = lambda dates, i : (dates.iloc[i+1] - dates.iloc[i]).days
	if num_dates >= seq_min_size :
		years = dates.dt.year
		for start_idx in range(num_dates - seq_min_size + 1) :
			result = None
			for end_idx in range(start_idx + seq_min_size - 1, num_dates) :
				years_span = years.iloc[end_idx] - years.iloc[start_idx]
				if years_span == seq_num_years - 1 : # E.g. 2007-2016 = 10 years
					# At least (n-1)*365 days from the first to the last measurement
					if (dates.iloc[end_idx] - dates.iloc[start_idx]).days >= (seq_num_years - 1) * 365 :
						if all(days_distance(dates,i) <= max_consecutive_days for i in range(start_idx, end_idx)) :
							result = (start_idx, end_idx)
						else :
							# Too wide a distance was found: skip to the next start index
							break
				elif years_span >= seq_num_years :
					break
			if not result is None :
				return result

def compute_cohorts() :
	logger.info("Querying for HbA1c measurements")
	query = f'''
		WITH valid_hba1c AS (
			SELECT idcentro, idana, data, valore
			FROM dati2.analisiemoglobinaglicata
			WHERE valore::float BETWEEN 5.5 AND 16
		),
		patients_with_enough_valid_hba1c AS (
			SELECT idcentro, idana
			FROM valid_hba1c
			WHERE EXTRACT(YEAR FROM data) BETWEEN { FIRST_YEAR } and { LAST_YEAR }
			GROUP BY idcentro, idana
			HAVING COUNT(*) > { SEQ_MIN_SIZE }
		)
		SELECT idcentro, idana, annodiagnosidiabete, data, valore
		FROM patients_with_enough_valid_hba1c
		JOIN valid_hba1c      USING (idcentro, idana)
		JOIN dati2.anagrafica USING (idcentro, idana)
		WHERE EXTRACT(YEAR FROM data) BETWEEN { FIRST_YEAR } AND { LAST_YEAR }
		AND annodiagnosidiabete IS NOT NULL
		AND annodiagnosidiabete::integer - annonascita::integer BETWEEN 18 AND 90 --Age at diagnosis 
		ORDER BY idcentro, idana, data;'''
	
	dtypes = {
		'annodiagnosidiabete': 'Int64',
		'valore' : 'float'
	}

	df = read_file_or_query(query=query, filename='all_hba1c_measurements.csv', dtype=dtypes)
	logger.info("#HbA1c measurements: %d" % len(df))

	logger.info("Creating cohorts...")

	df['data'] = pd.to_datetime(df['data'])
	grouped_df = df.groupby(PATIENT_KEY)

	cc_rows = []
	nc_rows = []
	for patient_id, group in grouped_df :
		if group['data'].is_monotonic_increasing :
			group.sort_values(by='data', inplace=True)
		indices = find_valid_subsequence(group['data'])
		if not indices is None :
			group['data'] = group['data'].dt.year
			subgroup = group.iloc[indices[0] : indices[1] + 1].drop(columns=["annodiagnosidiabete"])
			aggregated_row = (subgroup
				.groupby(PATIENT_KEY + ['data']) # Group by patient and date
				.agg("mean")                     # Calculate the mean of values
				.reset_index()                   # Flatten the grouped structure
				.groupby(PATIENT_KEY)            # Regroup by patient
				.agg(list)                       # Aggregate dates and values into lists
				.reset_index())                  # Flatten the final grouped structure
			
			cc_rows.append(aggregated_row)
			
			years = aggregated_row['data'].iloc[0]
			annodiagnosi = group['annodiagnosidiabete'].iloc[0]
			if not pd.isna(annodiagnosi) and years[0] - annodiagnosi <= NEODIAGNOSIS_YEARS :
				nc_rows.append(aggregated_row)

	def save_cohort_as_csv(cohort_rows, cohort_type) :
		cohort_df = pd.concat(cohort_rows)
		logger.info(f"#patients ({ cohort_type }): %d" % len(cohort_df))
		csv_filepath = get_data_filepath(f'measurements_{ cohort_type }.csv')
		cohort_df.to_csv(csv_filepath, index=False)

	save_cohort_as_csv(cc_rows, 'CC')
	save_cohort_as_csv(nc_rows, 'NC')

	logger.info("Done")

if __name__ == '__main__':
    compute_cohorts()