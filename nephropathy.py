from _utils import *
from materialization import materialize_dataset
import pandas as pd

nephropathy_csv_filepath = get_data_filepath('nephropathy.csv')

attribute2datatype = {
	'idcentro'   : 'integer',
	'idana'      : 'integer',
	'diagnosis'  : 'boolean',
	'onset_date' : 'date'
}

acr_thresholds = {
	"AMD023" : { "M" : 30,  "F" : 30 },
	"AMD024" : { "M" : 20,  "F" : 20 },
	"AMD111" : { "M" : 30,  "F" : 30 },
	"AMD026" : { "M" : 30,  "F" : 30 },
	"AMD910" : { "M" : 30,  "F" : 30 },
	"AMD911" : { "M" : 2.5, "F" : 3.5 }
}
GFR_CODE = "STITCH005"
GFR_THRESHOLD = 59

def get_candidates() :
	clusters_table_name = f'{CLUSTERING_DB_NAME}.clusters_cc'
	ACR_VALUES_SQL = ", ".join([f"'{ acr_code }'" for acr_code in acr_thresholds])
	query = f'''
		WITH labs as (
			SELECT
				idcentro, idana,
				data         AS lab_date,
				codicestitch AS lab_code,
				valore       AS lab_value
			FROM dati2.esamilaboratorioparametricalcolati
			JOIN { clusters_table_name }
			USING (idcentro, idana)
			WHERE codicestitch = '{ GFR_CODE }'
			UNION ALL
			SELECT
				idcentro, idana,
				data      AS lab_date,
				codiceamd AS lab_code,
				valore    AS lab_value
			FROM dati2.esamilaboratorioparametri
			JOIN { clusters_table_name }
			USING (idcentro, idana)
			WHERE codiceamd IN ( { ACR_VALUES_SQL } )
		)
		SELECT
			idcentro, idana, sesso AS sex,
			annoinizio AS cl_start_year,
			lab_date, lab_code, lab_value
		FROM { clusters_table_name }
		LEFT OUTER JOIN dati2.anagrafica USING (idcentro, idana)
		LEFT OUTER JOIN labs USING (idcentro, idana)
		ORDER BY idcentro, idana, lab_date;'''
	
	df = pd.read_sql(query, db_engine)
	
	df['cl_start_year'] = df['cl_start_year'].astype('Int64')
	df['lab_date'] = pd.to_datetime(df['lab_date'])
	df['lab_value'] = df['lab_value'].astype('float')
	return df

def evaluate_exclusion_criteria(date2diag, cl_start_year, cl_end_year) :
	last_diag = False
	alternation = False        # found P-N-...-N-P sequence
	temporary_positive = False # found P-...-P-N sequence
	num_labs = 0
	num_positive_tests = 0
	num_neg_after_pos = 0
	prev_positive = None
	for i, lab_date in enumerate(date2diag) :
		lab_year = lab_date.year
		if lab_year >= cl_start_year and lab_year <= cl_end_year :
			num_labs += 1
			curr_positive = date2diag[lab_date]

			if curr_positive == 1 :
				num_positive_tests += 1
				last_diag = True
			elif curr_positive == 0 :
				last_diag = False
				if num_positive_tests > 0 :
					num_neg_after_pos += 1

			if i > 0 and num_positive_tests > 1 :
				# The condition 'num_positive_tests > 1' holds for both cases, because:
				# - We tolerate one temporary positive value in a P-...-P-N sequence
				# - It is necessary to check P-N-...-N-P alternations
				if curr_positive == 1 and prev_positive == 0 and num_neg_after_pos > 1 :
					# The condition 'num_positive_tests > 1' holds for both cases, because
					# we tolerate one N in a P-N-...-N-P sequence
					alternation = True
				elif curr_positive == 0 and prev_positive == 1 :
					temporary_positive = True
			
			prev_positive = curr_positive
	return last_diag, num_labs, alternation, temporary_positive

def get_nephropathic_patients() :
	logger.info("Downloading patients' tests...")
	df = get_candidates()
	grouped_df = df.groupby(['idcentro','idana'])
	num_patients = len(grouped_df)
	logger.info(f"Downloaded data about { num_patients } patients")

	logger.info("Establishing nephropathy conditions...")
	num_positive = 0 # Certainly positive
	num_negative = 0 # Certainly negative
	num_excluded = 0 # Excluded patients
	num_early_stops = 0
	num_insufficient_labs = 0
	num_temporary_positives = 0
	num_positive_alternations = 0
	dataset = []

	# Iterate over all patients
	for (idcentro, idana), group in grouped_df :
		group = group.sort_values(by='lab_date').reset_index(drop=True)
		last_lab_year = None
		cl_start_year = None

		# Mapping date -> integer, where:
		# i = 1 indicates that all values for that date are positive
		# i = 0 indicates that all values for that date are negative
		# i = -1 indicates that only discordant ACR values for that date are present
		date2diag = dict()
		date2test = dict() # hierarchy: gfr > acr

		# Iterate over all labs
		for row in group.itertuples(index=False) :
			sex = row.sex
			lab_code = row.lab_code
			lab_value = row.lab_value
			lab_date = row.lab_date
			cl_start_year = row.cl_start_year
			last_lab_year = lab_date.year
			
			if lab_code in acr_thresholds :
				acr_threshold = acr_thresholds[lab_code][sex]
				acr_positive = 1 if lab_value >= acr_threshold else 0
				if lab_date not in date2diag :
					date2diag[lab_date] = acr_positive
					date2test[lab_date] = 'acr'
				elif date2test[lab_date] == 'acr' and date2diag[lab_date] != acr_positive :
					date2diag[lab_date] = -1
					
			elif lab_code == GFR_CODE :
				gfr_positive = 1 if lab_value <= GFR_THRESHOLD else 0
				if lab_date not in date2diag or date2test[lab_date] == 'acr':
					date2diag[lab_date] = gfr_positive
					date2test[lab_date] = 'gfr'
				elif date2test[lab_date] == 'gfr' and date2diag[lab_date] != gfr_positive :
					date2diag[lab_date] = -1
		
		onset_date = None
		num_positive_tests = 0
		for lab_date in date2diag :
			if date2diag[lab_date] == 1 :
				num_positive_tests += 1
				if onset_date is None :
					onset_date = lab_date
		
		cl_end_year = cl_start_year + CLUSTERING_YEARS - 1
		last_diag, num_labs, alternation, temporary_positive = evaluate_exclusion_criteria(date2diag, cl_start_year, cl_end_year)
		
		# Try to fix alternations and temporary positives considering only eGFR
		if alternation or temporary_positive :
			gfr_date2diag = {k: v for k, v in date2diag.items() if date2test[k] == 'gfr'}
			last_diag, _, alternation, temporary_positive = evaluate_exclusion_criteria(gfr_date2diag, cl_start_year, cl_end_year)

		early_stop = last_lab_year < cl_start_year + 4
		insufficient_labs = num_labs < 2

		if early_stop :
			num_early_stops += 1
		if insufficient_labs :
			num_insufficient_labs += 1
		if alternation :
			num_positive_alternations += 1
		if temporary_positive :
			num_temporary_positives += 1
		
		excluded_subject = early_stop or insufficient_labs or alternation or temporary_positive
		
		if excluded_subject :
			diagnosis = None
			num_excluded += 1
		elif last_diag :
			diagnosis = True
			num_positive += 1
		else :
			diagnosis = False
			num_negative += 1

		if not diagnosis :
			onset_date = None
		
		dataset.append([idcentro, idana, diagnosis, onset_date])
	
	assert len(dataset) == num_patients
	
	def log_count_and_perc(count, description) :
		perc = 100 * count / num_patients
		logger.info(f"Found {count} ({perc:.2f}%) {description}")
	
	log_count_and_perc(num_positive, 'positive patients')
	log_count_and_perc(num_negative, 'negative patients')
	log_count_and_perc(num_early_stops, 'patients with last event before the fifth year (excluded)')
	log_count_and_perc(num_insufficient_labs, 'patients with insufficient number of labs (excluded)')
	log_count_and_perc(num_positive_alternations, 'patients with alternating positive values (excluded)')
	log_count_and_perc(num_temporary_positives, 'patients with temporary diagnosis (excluded)')
	log_count_and_perc(num_excluded, 'total excluded patients')
	log_count_and_perc(num_positive + num_negative + num_excluded, 'checksum')

	assert num_patients == num_positive + num_negative + num_excluded

	logger.info("Exporting data as CSV...")
	output_df = pd.DataFrame(dataset, columns=attribute2datatype.keys())
	output_df.to_csv(nephropathy_csv_filepath, index=False)
	logger.info("Done")

def materialize_nephropathy_conditions() :
	materialize_dataset(
		csv_filepath = nephropathy_csv_filepath,
		table_name = NEPHROPATHY_TABLE,
		attribute2datatype = attribute2datatype
	)

if __name__ == '__main__':
	get_nephropathic_patients()
	materialize_nephropathy_conditions()