from _utils import *
from materialization import materialize_dataset
import psycopg2
import pandas as pd

retinopathy_csv_filepath = get_data_filepath('retinopathy.csv')
MIN_POSITIVE_DIAG = 2	# Minimum number of positive diagnosis per patient

attribute2datatype = {
	'idcentro'   : 'integer',
	'idana'      : 'integer',
	'diagnosis'   : 'boolean',
	'onset_date' : 'date'
}

retinopathy_diagnoses = ['AMD053', 'AMD054', 'AMD055', 'AMD056', 'AMD057', 'AMD204', 'AMD205', 'AMD210', 'AMD300']
non_retinopathy_diagnoses = ['AMD130']
screening_tests = ['AMD051', 'AMD052', 'AMD135']

def count_patients() :
	clusters_table_name = f'{CLUSTERING_DB_NAME}.clusters_cc'
	conn = psycopg2.connect(**db_config)
	cur = conn.cursor()
	cur.execute("SELECT COUNT(*) FROM " + clusters_table_name)
	count = cur.fetchone()[0]
	cur.close()
	conn.close()
	return count

def sql_strings_list(list) :
	return ', '.join([f"'{code}'" for code in list])

def get_candidates() :
	clusters_table_name = f'{CLUSTERING_DB_NAME}.clusters_cc'
	query = f'''
		WITH retinopathy_event AS (
			SELECT
				idcentro, idana, codiceamd AS event_code,
				data AS event_date, valore AS event_value
			FROM dati2.diagnosi
			JOIN { clusters_table_name }
			USING (idcentro, idana)
			WHERE codiceamd IN ({ sql_strings_list(retinopathy_diagnoses + non_retinopathy_diagnoses) })
			UNION ALL
			SELECT
				idcentro, idana, codiceamd AS event_code,
				data AS event_date, valore AS event_value
			FROM dati2.esamistrumentali
			JOIN { clusters_table_name }
			USING (idcentro, idana)
			WHERE codiceamd IN ({ sql_strings_list(screening_tests)})
		)
		SELECT
			idcentro, idana, cl_start_year,
			event_code, event_date, event_value
		FROM { clusters_table_name }
		LEFT OUTER JOIN (
			SELECT
				idcentro, idana, cl_start_year,
				event_code, event_date, event_value
			FROM (
				SELECT
					idcentro, idana, 
					annoinizio AS cl_start_year,
					annoinizio + { CLUSTERING_YEARS - 1 } AS cl_end_year
				FROM { clusters_table_name }
			) AS clusters
			JOIN retinopathy_event USING (idcentro, idana)
			JOIN (
				SELECT idcentro, idana, COUNT(*) AS count
				FROM retinopathy_event
				GROUP BY idcentro, idana
			) AS num_events USING (idcentro, idana)
			WHERE num_events.count > 2
			-- ignoring the following filter (the check is done later procedurally)
			-- AND EXTRACT(YEAR FROM event_date) BETWEEN cl_start_year and cl_end_year
		) events
		USING (idcentro, idana)
		ORDER BY idcentro, idana, event_date;'''
	
	df = pd.read_sql(query, db_engine)
	
	df['cl_start_year'] = df['cl_start_year'].astype('Int64')
	df['event_date'] = pd.to_datetime(df['event_date'])
	return df

def get_retinopathic_patients() :
	num_patients = count_patients()

	logger.info("Downloading patients' tests...")
	df = get_candidates()
	grouped_df = df.groupby(['idcentro', 'idana'])
	num_candidates = len(grouped_df)
	logger.info(f"Downloaded data about { num_candidates } patients")
	
	logger.info("Establishing retinopathy conditions...")
	num_positive = 0 # Certainly positive
	num_negative = 0 # Certainly negative
	num_temporary_positive = 0
	num_same_date_inconsistencies = 0
	num_long_screening_delays = 0
	num_early_stops = 0
	dataset = []

	# Iterate over all patients
	for (idcentro, idana), group in grouped_df :
		group = group.sort_values(by='event_date').reset_index(drop=True)

		(
			prev_date,
			prev_date_positive,
			onset_date,
			onset_year,
			last_screening_year,
			curr_date_positive,
			curr_date_neg_diagnosis,
			long_screening_delay,
			same_date_inconsistent_diagnosis,
			temporary_positive
		) = [None]*5 + [False]*5
		positive_tests = 0

		if len(group) >= MIN_POSITIVE_DIAG :
			# Iterate over all labs
			for row in group.itertuples(index=False) :
				event_date  = row.event_date
				event_code  = row.event_code
				event_value = row.event_value
				event_year  = event_date.year
				cl_start_year = row.cl_start_year

				# If it's the first entry, set the last screening year to
				# the year before the clustering's first year for the current patient
				# E.g. if the first year is 2006, then the following check should be true if
				# the first screening test found occurred in 2008.
				# In this case, last_screening_year should be set to 2005
				if last_screening_year is None :
					last_screening_year = event_year - 1
				
				# Check if there is a screening test at least every 2 years
				if event_year > last_screening_year + 2 :
					long_screening_delay = True
				
				# If the current event is a screening test, update the last screening year
				if event_code in screening_tests :
					last_screening_year = event_year

				# If a new date is reached, reset the data for the current date
				if event_date != prev_date :
					prev_date = event_date
					prev_date_positive = curr_date_positive
					curr_date_positive = False
					curr_date_neg_diagnosis = False
				
				# A negative diagnosis exists for the current date
				if event_code in non_retinopathy_diagnoses :
					curr_date_neg_diagnosis = True
				
				# If for the current date a negative and positive diagnosis is found,
				# then exit the loop
				if curr_date_neg_diagnosis and event_code in retinopathy_diagnoses :
					same_date_inconsistent_diagnosis = True
					#logger.warning(f"Inconsistent diagnosis for patient ({idcentro},{idana}) found on the same date ({event_date})")
				
				# A screening test/diagnosis is positive for the current date
				if event_value == 'P' or event_code in retinopathy_diagnoses :
					curr_date_positive = True
					positive_tests += 1
				
				if curr_date_positive and not prev_date_positive :
					onset_date = event_date
					onset_year = event_year
				elif (event_year >= cl_start_year and 
		  				not curr_date_positive and prev_date_positive) : #and onset_year != event_year :
					temporary_positive = True
		
		early_stop = event_year < cl_start_year + 4

		if temporary_positive :
			num_temporary_positive += 1
		if same_date_inconsistent_diagnosis :
			num_same_date_inconsistencies += 1
		if long_screening_delay :
			num_long_screening_delays += 1
		if early_stop :
			num_early_stops += 1

		excluded_subject = ( temporary_positive
			#or long_screening_delay
			#or same_date_inconsistent_diagnosis
			or early_stop )
		negative_subject = onset_date is None and not excluded_subject
		excluded_subject = excluded_subject or (positive_tests < MIN_POSITIVE_DIAG)
		if excluded_subject :
			onset_date = None
			onset_year = None
		positive_subject = not negative_subject and not excluded_subject

		diagnosis = None
		if negative_subject :
			diagnosis = False
			num_negative += 1
		elif positive_subject :
			diagnosis = True
			num_positive += 1
		dataset.append([idcentro, idana, diagnosis, onset_date])
	
	assert len(dataset) == num_candidates
	
	def log_count_and_perc(count, description) :
		perc = 100 * count / num_patients
		logger.info(f"Found {count} ({perc:.2f}%) {description}")
	
	log_count_and_perc(num_positive, 'positive patients')
	log_count_and_perc(num_negative, 'negative patients')
	log_count_and_perc(num_long_screening_delays, 'patients with a delay between screening tests greater than 2 years')
	log_count_and_perc(num_temporary_positive, 'patients with temporary diagnosis')
	log_count_and_perc(num_same_date_inconsistencies, 'patients with contradicting diagnoses in the same date')
	log_count_and_perc(num_early_stops, 'patients with last event before the fifth year')

	logger.info("Exporting data as CSV...")
	output_df = pd.DataFrame(dataset, columns=attribute2datatype.keys())
	output_df.to_csv(retinopathy_csv_filepath, index=False)
	logger.info("Done")

def materialize_retinopathy_conditions() :
	materialize_dataset(
		csv_filepath = retinopathy_csv_filepath,
		table_name = RETINOPATHY_TABLE,
		attribute2datatype = attribute2datatype
	)

if __name__ == '__main__':
	get_retinopathic_patients()
	materialize_retinopathy_conditions()