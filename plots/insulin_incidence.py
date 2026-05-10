from _utils import *
from materialization import materialize_dataset
from plots._utils import *
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def plot_insulin_cumulative_incidences(store_tti = False) :
	for cohort in ['CC', 'NC'] :
		logger.info(f'Plotting cumulative incidence of insuline prescriptions for cohort {cohort}')
		table_name = f'{CLUSTERING_DB_NAME}.clusters_{cohort.lower()}'
		
		query = f'''
			WITH clusters AS (
				SELECT
					idcentro, idana,
					cluster,
					CAST(CONCAT(annoinizio, '-01-01') AS DATE) AS start_date,
					CAST(CONCAT(annoinizio, '-12-31') AS DATE) + INTERVAL '{ CLUSTERING_YEARS - 1 } years' AS end_date
				FROM { table_name }
			),
			insulin_prescriptions_during_cluster_period AS (
				SELECT
					idcentro, idana,
					pre.data
				FROM clusters
				JOIN dati2.prescrizionidiabetefarmaci pre USING (idcentro, idana)
				WHERE LEFT(pre.codiceatc, 4) = 'A10A'
				AND pre.data BETWEEN clusters.start_date AND clusters.end_date
			),
			first_insulin_prescription AS (
				SELECT
					idcentro, idana,
					MIN(data) AS date
				FROM dati2.prescrizionidiabetefarmaci
				WHERE LEFT(codiceatc, 4) = 'A10A'
				GROUP BY idcentro, idana
			)
			SELECT
				idcentro, idana,
				clusters.cluster,
				clusters.start_date AS cl_start_date,
				EXTRACT(YEAR FROM clusters.end_date) AS cl_end_year,
				first_insulin_prescription.date AS first_insulin_date,
				pre.data AS insulin_prescr_date
			FROM clusters
			LEFT OUTER JOIN insulin_prescriptions_during_cluster_period pre USING (idcentro, idana)
			LEFT OUTER JOIN first_insulin_prescription USING (idcentro, idana)
			WHERE first_insulin_prescription.date IS NULL OR
			      first_insulin_prescription.date >= clusters.start_date
			ORDER BY cluster, idcentro, idana, insulin_prescr_date;'''
		
		df = pd.read_sql_query(query, db_engine)
		logger.info(f'Completed download of { cohort } cohort\'s data')
		check_dataframe_columns(df, [
			'idcentro', 'idana', 'cluster', 'cl_start_date', 'cl_end_year', 'insulin_prescr_date'
		])
		df["cl_end_year"]         = df["cl_end_year"].astype(int)
		df["cl_start_date"]       = pd.to_datetime(df["cl_start_date"])
		df["first_insulin_date"]  = pd.to_datetime(df["first_insulin_date"])
		df["insulin_prescr_date"] = pd.to_datetime(df["insulin_prescr_date"])

		def has_consistent_insuline_prescription_history(group, years_tolerance=1) :
			"""
			Parameters:
				group: The group representing the history of prescriptions of a subject.
				years_tolerance (int): The maximum number of years that is accepted
				                       between two subsequent prescriptions.

			Returns:
				bool: True if the group contains a "consistent" series of insuline prescriptions;
				      False if the subject must be excluded from the statistics.
			"""
			
			# Sort dates in ascending order
			sorted_group = group.sort_values('insulin_prescr_date')
			
			# The subject must be excluded if there exists at least one insulin prescription
			# but the last date's year does not match the end_year
			if not group['insulin_prescr_date'].isna().all() :
				last_date_year = sorted_group['insulin_prescr_date'].dt.year.iloc[-1]
				end_year = group['cl_end_year'].iloc[0]
				if last_date_year != end_year :
					return False
			
			# Loop through the dates in reverse order
			for i in range(len(sorted_group)-1, 0, -1) :
				current_date = sorted_group.iloc[i]['insulin_prescr_date']
				prev_date = sorted_group.iloc[i - 1]['insulin_prescr_date']

				# Check if the year difference exceeds the tolerance
				if current_date.year - prev_date.year > years_tolerance + 1 :
					return False

			return True

		def get_insuline_start_date(group) :
			"""
			This function retrieves the date of the first insuline prescription in the
			clustering period for the given subject.
			
			Parameters:
				group: The group representing the history of prescriptions of a subject.
			"""

			def build_result(value) :
				return pd.Series([value])
			
			if group['insulin_prescr_date'].isna().all() :
				return build_result(pd.NaT)
			
			'''# Patients for which the first insulin date (in the whole dataset) precedes
			# the first insluin during the clustering pediod should not be considered
			# for computing the "time to insulin".
			first_insulin_date_in_clustering_period = group['insulin_prescr_date'].min()
			if group['first_insulin_date'].iloc[0] < first_insulin_date_in_clustering_period :
				return build_result(pd.NaT)'''
			
			# Sort dates in ascending order
			sorted_group = group.sort_values('insulin_prescr_date')
			
			'''
			# Loop through the dates in reverse order
			for i in range(len(sorted_group)-1, 0, -1) :
				current_date = sorted_group.iloc[i]['insulin_prescr_date']
				prev_date = sorted_group.iloc[i - 1]['insulin_prescr_date']

				# Check if the year difference exceeds the tolerance
				if current_date.year - prev_date.year > years_tolerance + 1 :
					return build_result(current_date)  # Get the "last first" date (ignoring the previous ones)
			'''

			return build_result(sorted_group.iloc[0]['insulin_prescr_date'])

		def store_time_to_insulin(df) :
			output_table_name = "time_to_insulin"

			df_to_save = df[[
				'idcentro',
				'idana',
				'insulin_start_date',
				'time_to_insulin_days'
			]].copy()
			df_to_save['time_to_insulin_days'] = df_to_save['time_to_insulin_days'].astype('Int64')

			materialize_dataset(
				df=df_to_save,
				table_name=output_table_name,
				attribute2datatype={
					'idcentro': 'INTEGER',
					'idana': 'INTEGER',
					'insulin_start_date': 'DATE',
					'time_to_insulin_days': 'INTEGER'
				},
				create_index_on_patient_key=True
			)
			logger.info(f"Saved time to insulin to {CLUSTERING_DB_NAME}.{output_table_name}")
		
		grouping_columns = ['idcentro', 'idana', 'cluster', 'cl_start_date']
		df = (df.groupby(grouping_columns)
				.filter(has_consistent_insuline_prescription_history)
				.groupby(grouping_columns)
				.apply(get_insuline_start_date)
				.reset_index()
				.rename(columns={0: 'insulin_start_date'}))
		
		df['time_to_insulin_days'] = (df['insulin_start_date'] - df['cl_start_date']).dt.days
		df['time_to_insulin_year_fraction'] = df['time_to_insulin_days'] / 365.25

		if cohort == 'CC' and store_tti :
			store_time_to_insulin(df)

		df.sort_values(by=['cluster','time_to_insulin_year_fraction'], inplace=True)
		cumulative_incidence = df.groupby('cluster').apply(
			lambda g: g['time_to_insulin_year_fraction'].notnull().cumsum()
		).reset_index(level=0, drop=True)

		cluster_counts = df['cluster'].map(
			df.groupby('cluster').size()
		)
		
		df['perc_cumulative_incidence'] = cumulative_incidence / cluster_counts * 100

		logger.debug(df)
		plt.figure(figsize=(6, 5))
		for cluster, group in df.groupby('cluster') :
			logger.info(f'Plotting cluster: { cluster }')
			plt.plot(
				group['time_to_insulin_year_fraction'],
				group['perc_cumulative_incidence'],
				label=cluster_inline_labels[cluster],
				color=cluster_colors[cluster],
				linestyle=cluster_linestyles[cluster]
			)
			logger.info(f'Cumulative incidence at {CLUSTERING_YEARS}-th year for cluster {cluster} (%): ' + 
				str(group['perc_cumulative_incidence'].tail(1).iloc[-1]))

		plot_limit_y = 100
		
		# Plot horizontal lines at multiples of 10%
		for percentage in range(10, plot_limit_y, 10) :
			plt.axhline(y=percentage, color='gray', linestyle='-', linewidth=0.5, alpha=0.7)
		
		# Set tickst from 0 to 10 each 1 units
		ax = plt.gca()
		ax.set_xticks(np.arange(0, CLUSTERING_YEARS + 1, 1))
		
		# Set plot title and labels
		plt.title(f'Insulin cumulative incidence ({cohort})')
		plt.suptitle('')  # Remove the default title to avoid overlap
		plt.xlabel('years')
		plt.ylabel('subjects %')
		#plt.subplots_adjust(bottom=0.15)  # Increase bottom margin
		plt.xlim(-0.2, CLUSTERING_YEARS + 0.2)
		plt.ylim(0, plot_limit_y)

		handles, labels = ax.get_legend_handles_labels()
		legend_order = [0,1,3,2]
		legend_x = 0
		legend_y = 0.714 if cohort == 'CC' else 0.78
		legend_w = 0.65
		legend_h = 0.2
		plt.legend(
			[handles[idx] for idx in legend_order], [labels[idx] for idx in legend_order],
			handlelength=3,
			bbox_to_anchor=(legend_x, legend_y, legend_w, legend_h),  # x0, y0, width, height in axes‐fraction units
			mode='expand',
			borderpad=0.5
		)
		
		# Save the plot as an SVG file
		svg_filepath = get_plot_filepath(f'insulin_cumulative_incidence_{cohort}.svg')
		plt.savefig(svg_filepath, format='svg', bbox_inches='tight')
		logger.info('Saved plot to: ' + svg_filepath)
