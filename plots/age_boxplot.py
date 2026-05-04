from _utils import db_engine, logger, CLUSTERING_DB_NAME
from plots._utils import *
import pandas as pd
import matplotlib.pyplot as plt
from math import ceil

FONT_SIZE = 11
PLOT_P_VALUES = True
signif = {
	'CC': [ (0, 1, None), (0, 2, None), (0, 3, None), (1, 2, None), (1, 3, None), (2, 3, None) ],
	'NC': [ (0, 1, None), (0, 2, None), (0, 3, None), (1, 2, 0.506),  (1, 3, None), (2, 3, None) ],
}

def plot_boxplots(query, cohort) :
	"""
	Executes an SQL query to fetch data from a PostgreSQL database and creates boxplots for each cluster.

	:param query: SQL query to execute
	:param cohort: 'CC' or 'NC'
	"""
	df = pd.read_sql_query(query, db_engine)
	check_dataframe_columns(df, ['cluster', 'age_at_diagnosis'])
	assert set(df['cluster']) == set(cluster_ordering)
	
	_, ax = plt.subplots()
	plt.rcParams.update({'font.size': FONT_SIZE})

	# Loop through each cluster
	for index, cluster in enumerate(cluster_ordering) :
		# Filter data for the current clustercluster
		subset = df[df['cluster'] == cluster]
		facecolor = 'white' if COLOR == 'bw' else cluster_colors[cluster]
		
		# Create a boxplot for this subset
		# We use index to avoid overlapping; here indexes are arbitrary
		bp = ax.boxplot(subset['age_at_diagnosis'], positions=[index],
						patch_artist=True, widths=0.4,
						boxprops=dict(facecolor=facecolor, color='black'),
						#whiskerprops=dict(color=color),
						#capprops=dict(color=color),
						medianprops=dict(color='black'),
						flierprops=dict(marker='o'))
	
	if PLOT_P_VALUES :
		y_start = 0
		for idx, cluster in enumerate(cluster_ordering) :
			subset = df[df['cluster'] == cluster]['age_at_diagnosis']
			q3 = subset.quantile(0.75)
			if q3 > y_start :
				y_start = q3
		
		tick_h_distance = 0.05
		h = (df['age_at_diagnosis'].max() - df['age_at_diagnosis'].min()) * 0.05

		assigned = []
		for (i, j, p) in signif[cohort] :
			if p is not None :
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
	
	# Change the aspect ratio in order to fix the plot's width
	ax.set_aspect(0.045)
	
	# Set x-ticks to match the clusters
	ax.set_xticks(range(len(cluster_ordering)))
	ax.set_xticklabels([cluster_multiline_labels[cluster] for cluster in cluster_ordering])
	plt.tick_params(axis='both', labelsize=FONT_SIZE)

	y_lower_limit = 14
	y_upper_limit = 93

	# Plot horizontal lines at integer ages
	for age in range(ceil(y_lower_limit/10)*10, ceil(y_upper_limit/10)*10, 10) :
		plt.axhline(y=age, color='lightgray', linestyle='-', linewidth=0.5, alpha=0.7)
	
	# Set plot title and labels
	plt.title(f'Age distribution by cluster ({cohort})')
	plt.suptitle('')  # Remove the default title to avoid overlap
	#plt.xlabel('Cluster')
	if cohort == 'CC':
		plt.ylabel('years')
	#plt.subplots_adjust(bottom=0.15)  # Increase bottom margin
	plt.ylim(y_lower_limit, y_upper_limit)
	
	# Save the plot as an SVG file
	svg_filepath = get_plot_filepath(f'age_boxplots_{cohort}.svg')
	plt.savefig(svg_filepath, format='svg', bbox_inches='tight')

# Exported function
def plot_age_boxplots() :
	for cohort in ['CC', 'NC'] :
		logger.info(f'Making age boxplot for cohort {cohort}')
		cluster_table_name = f'{CLUSTERING_DB_NAME}.clusters_{cohort.lower()}'
		query = f'''
			SELECT
				cluster,
				annodiagnosidiabete::integer - annonascita::integer AS age_at_diagnosis
			FROM dati2.anagrafica
			JOIN { cluster_table_name }
			USING (idcentro, idana)
			WHERE annodiagnosidiabete IS NOT NULL;'''

		plot_boxplots(query, cohort)
