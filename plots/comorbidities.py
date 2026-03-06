from _utils import *
from plots._utils import *
from matplotlib.ticker import MaxNLocator
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def plot_comorbidities_cumulative_incidences() :
	for comorbidity, plot_limit_y in [(NEPHROPATHY_TABLE, 22), (RETINOPATHY_TABLE, 35)] :

		for cohort in ['CC', 'NC'] :
			cluster_table_name = f'{CLUSTERING_DB_NAME}.clusters_{cohort.lower()}'
			comorbidity_table_name = f'{CLUSTERING_DB_NAME}.{comorbidity}'
			
			query = f'''
				-- The check onset_date >= annoinizio is necessary for computing
				-- the incidence (not the prevalence!) of the comorbidity
				SELECT
					idcentro, idana, cluster, onset_date,
					CAST(CONCAT(annoinizio, '-01-01') AS DATE) AS cl_start_date
				FROM { cluster_table_name }
				LEFT OUTER JOIN { comorbidity_table_name } AS comorbidity USING (idcentro, idana)
				WHERE comorbidity.diagnosis IS NOT NULL
				    AND (NOT comorbidity.diagnosis OR EXTRACT(YEAR FROM onset_date) >= annoinizio)
				ORDER BY cluster, idcentro, idana, onset_date;'''
			
			df = pd.read_sql_query(query, db_engine)
			logger.info(f'Completed download of data about { comorbidity }')
			check_dataframe_columns(df, [
				'idcentro', 'idana', 'cl_start_date', 'onset_date'
			])
			for col in ['onset_date', 'cl_start_date'] :
				df[col] = pd.to_datetime(df[col])
			
			df['time_to_comorbidity_year_fraction'] = (
				(df['onset_date'] - df['cl_start_date']).dt.days / 365.25
			)
			df.sort_values(by=['cluster','time_to_comorbidity_year_fraction'], inplace=True)

			cumulative_incidence = df.groupby('cluster').apply(
				lambda g: g['time_to_comorbidity_year_fraction'].notnull().cumsum()
			).reset_index(level=0, drop=True)

			cluster_counts = df['cluster'].map(
				df.groupby('cluster').size()
			)
			
			df['perc_cumulative_incidence'] = cumulative_incidence / cluster_counts * 100

			logger.debug(df)
			plt.figure(figsize=(6, 5))
			for cluster, group in df.groupby('cluster') :
				logger.info(f'Plotting cluster: { cluster }')
				first_ten_years = group[group['time_to_comorbidity_year_fraction'].notna() &
					                   (group['time_to_comorbidity_year_fraction'] <= CLUSTERING_YEARS)]
				plt.plot(
					first_ten_years['time_to_comorbidity_year_fraction'],
					first_ten_years['perc_cumulative_incidence'],
					label=cluster_inline_labels[cluster],
					color=cluster_colors[cluster],
					linestyle=cluster_linestyles[cluster]
				)
				logger.info(f'Cumulative incidence at {CLUSTERING_YEARS}-th year for cluster {cluster} (%): ' + 
					str(first_ten_years['perc_cumulative_incidence'].tail(1).iloc[-1]))
			
			# Plot horizontal lines
			hrow_delta = 10 if comorbidity == 'retinopathy' else 5
			for percentage in range(hrow_delta, plot_limit_y, hrow_delta) :
				plt.axhline(y=percentage, color='gray', linestyle='-', linewidth=0.5, alpha=0.7)
			
			# Set ticks from 0 to 10 each 1 units
			ax = plt.gca()
			ax.set_xticks(np.arange(0, CLUSTERING_YEARS + 1, 1))
			ax.set_yticks(np.arange(0, 21, 5))

			# Set plot title and labels
			plt.title(f'{ucfirst(comorbidity)} culumative incidence ({cohort})')
			plt.suptitle('')  # Remove the default title to avoid overlap
			plt.xlabel('years')
			plt.ylabel('subjects %')
			#plt.subplots_adjust(bottom=0.15)  # Increase bottom margin
			plt.xlim(-0.2, CLUSTERING_YEARS + 0.2)
			plt.ylim(0, plot_limit_y)

			handles, labels = ax.get_legend_handles_labels()
			legend_order = [0,1,3,2]
			legend_x = 0
			legend_y = 0.714 if cohort == 'CC' and comorbidity == 'retinopathy' else 0.78
			legend_w = 0.65
			legend_h = 0.18 if cohort == 'CC' and comorbidity == 'retinopathy' else 0.2
			plt.legend(
				[handles[idx] for idx in legend_order], [labels[idx] for idx in legend_order],
				handlelength=3,
				bbox_to_anchor=(legend_x, legend_y, legend_w, legend_h),  # x0, y0, width, height in axes‐fraction units
				mode='expand',
				borderpad=0.5
			)
			
			# Save the plot as an SVG file
			svg_filepath = get_plot_filepath(f'{comorbidity}_cumulative_incidence_{cohort}.svg')
			plt.savefig(svg_filepath, format='svg', bbox_inches='tight')
			logger.info('Saved plot to: ' + svg_filepath)
