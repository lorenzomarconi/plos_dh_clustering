from _utils import get_data_filepath, CLUSTERING_YEARS
from plots._utils import *
import pandas as pd
import matplotlib.pyplot as plt

def polt_trends(cohort, show_standard_deviation=False) :
	# Read the CSV file
	data = pd.read_csv(get_data_filepath(f'clusters_{ cohort }.csv'), header=0)
	data.drop(['idcentro', 'idana', 'annoinizio'], axis=1, inplace=True)

	# Assuming the last column is the label and the rest are measurements
	for col in data.columns[0:CLUSTERING_YEARS] :
		data[col] = data[col].astype(float)
	# Group by the label and calculate the mean of each measurement column
	averages = data.groupby('cluster').mean().reset_index()
	std_devs = data.groupby('cluster').std().reset_index()
	
	print(f"Plotting HbA1c trends for cohort: {cohort}")
	print(averages.T)
	print(std_devs.T)
	
	# Changing the aspect ratio
	plt.figure(figsize=(7, 4))

	for row_index, row in averages.iterrows() :
		cluster = row['cluster']
		label = cluster_inline_labels[cluster]
		color = cluster_colors[cluster]
		year_indices = [s[1:] for s in row.index[1:]]
		
		if show_standard_deviation :
			plt.errorbar(x=year_indices, y=row[1:], yerr=std_devs.iloc[row_index][1:], fmt='o-',
						label=label, color=color, ecolor=color, elinewidth=1, capsize=5)
		else :
			plt.plot(
				year_indices,
				row[1:],
				marker=cluster_markers[cluster],
				label=label,
				color=color,
				linestyle=cluster_linestyles[cluster]
			)
	
	# Plot horizontal lines at multiples of 10%
	for percentage in range(7, 12, 1) :
		plt.axhline(y=percentage, color='gray', linestyle='-', linewidth=0.5, alpha=0.7)

	# Plotting
	plt.title(f'Average {A1C_LABEL} by year per cluster ({ cohort })')
	plt.suptitle('')  # Remove the default title to avoid overlap
	plt.xlabel('year')
	plt.ylabel(f'{A1C_LABEL} %')
	plt.xticks(rotation=45)

	handles, labels = plt.gca().get_legend_handles_labels()
	legend_order = [0,1,3,2]
	plt.legend(
		[handles[idx] for idx in legend_order], [labels[idx] for idx in legend_order],
		handlelength=3
	)

	svg_filepath = get_plot_filepath(f'hba1c_trends_{ cohort }.svg')
	plt.tight_layout()
	plt.ylim(6 if show_standard_deviation else 6.5, 11.4)
	plt.savefig(svg_filepath, format='svg', bbox_inches='tight')

# Exported function
def plot_hba1c_trends() :
	for cohort in ['CC', 'NC'] :
		polt_trends(cohort)
