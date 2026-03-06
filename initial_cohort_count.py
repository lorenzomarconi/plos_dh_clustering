from _utils import db_engine, logger, FIRST_YEAR, LAST_YEAR
import pandas as pd

"""
This script is just used for computing the initial number of patients.
"""

def run() :
	query = '''
	-- Initial set of patients
	SELECT
	p.*, ge.values_array, ge.mean_value, ge.date_array 
	FROM
	dati2.anagrafica AS p
	JOIN (SELECT idcentro, idana,
				AVG(CAST(valore AS float)) AS mean_value,
				ARRAY_AGG(valore ORDER BY data) AS values_array,
				ARRAY_AGG(data ORDER BY data) AS date_array
		FROM dati2.analisiemoglobinaglicata
		WHERE EXTRACT(year FROM data) BETWEEN %d and %d
		GROUP BY idcentro, idana) AS ge
	USING (idcentro, idana);
	''' % (FIRST_YEAR, LAST_YEAR)

	df = pd.read_sql(query, db_engine)
	logger.info(f"Size of initial cohort: { len(df) }")

if __name__ == '__main__':
	run()