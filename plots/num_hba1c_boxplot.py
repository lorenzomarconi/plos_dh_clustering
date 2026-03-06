from _utils import *
from plots._utils import *
import pandas as pd
import matplotlib.pyplot as plt
from math import ceil

FONT_SIZE = 11
PLOT_P_VALUES = True
signif = {
	'CC': [ (0, 2, None), (0, 1, None), (0, 3, None), (1, 2, 0.841), (1, 3, None), (2, 3, None) ],
	'NC': [ (0, 2, None), (0, 1, None), (0, 3, None), (1, 2, 0.019),  (1, 3, None), (2, 3, None) ],
}

def plot_boxplots(query, cohort) :
	"""
	Executes an SQL query to fetch data from a PostgreSQL database and creates boxplots for each cluster.

	:param query: SQL query to execute
	:param cohort: 'CC' or 'NC'
	"""
	df = pd.read_sql_query(query, db_engine)
	check_dataframe_columns(df, ['cluster', 'num_hba1c_measurements'])
	assert set(df['cluster']) == set(cluster_ordering)
	
	_, ax = plt.subplots()
	
	# Loop through each cluster
	for index, cluster in enumerate(cluster_ordering) :
		# Filter data for the current cluster
		subset = df[df['cluster'] == cluster]
		facecolor = 'white' if COLOR == 'bw' else cluster_colors[cluster]
		
		# Create a boxplot for this subset
		# We use index to avoid overlapping; here indexex are arbitrary
		bp = ax.boxplot(subset['num_hba1c_measurements'], positions=[index],
						patch_artist=True, widths=0.5,
						boxprops=dict(facecolor=facecolor, color='black'),
						#whiskerprops=dict(color=color),
						#capprops=dict(color=color),
						medianprops=dict(color='black'),
						flierprops=dict(marker='o'))
	
	if PLOT_P_VALUES :
		y_start = 0
		for idx, cluster in enumerate(cluster_ordering) :
			subset = df[df['cluster'] == cluster]['num_hba1c_measurements']
			q3 = subset.quantile(0.75)
			if q3 > y_start :
				y_start = q3
		
		tick_h_distance = 0.05
		h = (df['num_hba1c_measurements'].max() - df['num_hba1c_measurements'].min()) * 0.05

		assigned = []
		for (i, j, p) in signif[cohort] :
			if p is not None :
				if (i,j) == (0, 2) : # Particular case
					lvl = -1
				else :
					lvl = 0
					while any(not (j <= ii or i >= jj) and level == lvl
							for ii, jj, level in assigned) :
						lvl += 1
				assigned.append((i, j, lvl))
				
				y = y_start + h * (lvl + 0.25)
				tick_height = h - 0.5
				half_th = tick_height / 2
				h_start = i + tick_h_distance
				h_end = j - tick_h_distance
				v_start = y + 0.5
				v_end = y + tick_height
				ax.plot([h_start,h_start], [v_start,v_end], lw=1, color='black')                 # left vertical tick
				ax.plot([h_end,  h_end], [v_start,v_end], lw=1, color='black')                   # right vertical tick
				ax.plot([h_start,h_end], [v_start+half_th,v_start+half_th], lw=1, color='black') # horizontal line
				ax.text(
					(i + j) / 2, y + h/2 * 1.1,
					f"p = {p:.3f}" if p is not None else f"p < 0.05",
					ha='center', va='bottom',
					fontsize=FONT_SIZE-2
				)
	
	# Set x-ticks to match the clusters
	ax.set_xticks(range(len(cluster_ordering)))
	ax.set_xticklabels([cluster_multiline_labels[cluster] for cluster in cluster_ordering])
	plt.tick_params(axis='both', labelsize=FONT_SIZE)
	
	y_lower_limit = 8
	y_upper_limit = 75
	# Change the aspect ratio in order to fix the plot's width
	ax.set_aspect(0.055)

	# Plot horizontal lines at integer values
	for int_val in range(ceil(y_lower_limit/10)*10, ceil(y_upper_limit/10)*10, 10) :
		plt.axhline(y=int_val, color='gray', linestyle='-', linewidth=0.5, alpha=0.7)
	
	# Set plot title and labels
	plt.title(f'Number of {A1C_LABEL} measurements by cluster ({cohort})')
	plt.suptitle('')  # Remove the default title to avoid overlap
	#plt.xlabel('Cluster')
	#if cohort == 'CC':
	#	plt.ylabel('lateral label')
	#plt.subplots_adjust(bottom=0.15)  # Increase bottom margin
	plt.ylim(y_lower_limit, y_upper_limit)
	
	# Save the plot as an SVG file
	svg_filepath = get_plot_filepath(f'num_hba1c_boxplots_{cohort}.svg')
	plt.savefig(svg_filepath, format='svg', bbox_inches='tight')

# Exported function
def plot_num_hba1c_boxplots() :
	for cohort in ['CC', 'NC'] :
		cluster_table_name = f'{CLUSTERING_DB_NAME}.clusters_{cohort.lower()}'
		query = f'''
			WITH clusters AS (
					SELECT
							idcentro, idana,
							cluster,
							CAST(CONCAT(annoinizio, '-01-01') AS DATE) AS start_date,
							CAST(CONCAT(annoinizio, '-12-31') AS DATE) + INTERVAL '{ CLUSTERING_YEARS - 1 } years' AS end_date
					FROM { cluster_table_name }
			),
			cluster_counts AS (
					SELECT cluster, COUNT(*) AS num_patients
					FROM { cluster_table_name }
					GROUP BY cluster
			),
			dates_with_hba1c AS (
					SELECT DISTINCT cluster, idcentro, idana, data
					FROM dati2.esamilaboratorioparametri
					JOIN clusters USING (idcentro,idana)
					WHERE data BETWEEN start_date AND end_date
					AND codiceamd IN ('AMD008', 'AMD305')
			)
			SELECT
				cluster,
				CASE
					WHEN (idcentro, idana) NOT IN (SELECT idcentro, idana FROM dates_with_hba1c)
					THEN 0 ELSE COUNT(*)::DECIMAL
				END AS num_hba1c_measurements
			FROM dates_with_hba1c
			JOIN cluster_counts USING (cluster)
			RIGHT JOIN clusters USING (cluster,idcentro,idana)
			GROUP BY cluster, num_patients, idcentro, idana
			ORDER BY cluster, num_hba1c_measurements;'''

		plot_boxplots(query, cohort)
