from _utils import db_engine, logger, CLUSTERING_DB_NAME
from plots._utils import *
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from math import ceil

TOTAL_NAME = 'Total'
TOTAL_RESULTS = False
FONT_SIZE = 11
PLOT_P_VALUES = True
signif = {
	'CC': [ (0, 1, None), (0, 2, None), (0, 3, None), (1, 2, 0.646), (1, 3, None), (2, 3, None) ],
	'NC': [ (0, 1, 0.012), (0, 2, None), (0, 3, None), (1, 2, None),  (1, 3, None), (2, 3, 0.860) ],
}

def plot_histograms(query, cohort) :
	"""
	Executes an SQL query to fetch data from a PostgreSQL database and creates histograms for each cluster.

	:param query: SQL query to execute
	:param cohort: 'CC' or 'NC'
	"""
	df = pd.read_sql_query(query, db_engine)
	check_dataframe_columns(df, ['cluster', 'sex'])
	#assert set(df['cluster']) == set(cluster_ordering)

	# Computing % for each cluster and sex
	df['perc'] = df['count'] / df.groupby('cluster')['count'].transform('sum') * 100
	xlabels = (cluster_ordering + [TOTAL_NAME]) if TOTAL_RESULTS else cluster_ordering
	df['cluster'] = pd.Categorical(df['cluster'], categories=xlabels, ordered=True)
	df = df.sort_values(['cluster', 'sex'])

	# Preparing clusters for plotting them
	males = df[df['sex'] == 'M']['perc'].values
	females = df[df['sex'] == 'F']['perc'].values
	
	_, ax = plt.subplots()
	plt.rcParams.update({'font.size': FONT_SIZE})
	width = 0.35
	x = np.arange(5)
	hatch_f = '///'
	hatch_m = ''

	# Loop through each cluster
	for i, cluster in enumerate(xlabels) :
		facecolor = 'lightgrey' if COLOR == 'bw' or cluster not in cluster_colors \
			               else cluster_colors[cluster]

		ax.bar(x[i] - width/2, females[i], width, hatch=hatch_f, color=facecolor, edgecolor='black')
		ax.bar(x[i] + width/2, males[i], width, hatch=hatch_m, color=facecolor, edgecolor='black')
	
	if PLOT_P_VALUES :
		y_start = df['perc'].max()
		
		default_lvl = 0
		tick_h_distance = 0.05
		h = 4
		assigned = []
		for (i, j, p) in signif[cohort] :
			if p is not None :
				lvl = default_lvl
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
	ax.set_xticks(range(len(xlabels)))
	multiline_xlabels = [cluster_multiline_labels[cluster] for cluster in cluster_ordering]
	ax.set_xticklabels((multiline_xlabels + [TOTAL_NAME]) if TOTAL_RESULTS else multiline_xlabels)
	plt.tick_params(axis='both', labelsize=FONT_SIZE)

	y_lower_limit = 25
	y_upper_limit = 72 if PLOT_P_VALUES else 65

	# Plot horizontal lines
	for perc in range(ceil(y_lower_limit/10)*10, ceil(y_upper_limit/10)*10, 10) :
		plt.axhline(y=perc, color='lightgrey', linestyle='-', linewidth=0.5, alpha=0.7)
	
	# Set plot title and labels
	plt.title(f'Sex distribution by cluster ({cohort})')
	plt.suptitle('')  # Remove the default title to avoid overlap
	#plt.xlabel('cluster')
	plt.ylabel('subjects %')
	#plt.subplots_adjust(bottom=0.15)  # Increase bottom margin
	plt.ylim(y_lower_limit, y_upper_limit)

	from matplotlib.patches import Patch
	legend_elements = [
		Patch(facecolor='lightgrey', hatch=hatch_f, edgecolor='black', label='Females'),
		Patch(facecolor='lightgrey', hatch=hatch_m, edgecolor='black', label='Males')
	]
	ax.legend(handles=legend_elements, ncol=2, loc='upper right') #, title="Sex")
	
	# Save the plot as an SVG file
	svg_filepath = get_plot_filepath(f'sex_histograms_{cohort}.svg')
	plt.savefig(svg_filepath, format='svg', bbox_inches='tight')

# Exported function
def plot_sex_histograms() :
	for cohort in ['CC', 'NC'] :
		logger.info(f'Making sex histogram for cohort {cohort}')
		cluster_table_name = f'{CLUSTERING_DB_NAME}.clusters_{cohort.lower()}'
		total_query = f'''
			UNION ALL
			SELECT
				'{ TOTAL_NAME }' AS cluster,
				sesso AS sex,
				COUNT(*) AS count'''
		query = f'''
			SELECT
				cluster,
				sesso AS sex,
				COUNT(*) AS count
			FROM dati2.anagrafica
			JOIN { cluster_table_name }
			USING (idcentro, idana)
			GROUP BY sesso, cluster
			{ total_query }
			FROM dati2.anagrafica
			JOIN { cluster_table_name }
			USING (idcentro, idana)
			GROUP BY sesso;'''

		plot_histograms(query, cohort)
