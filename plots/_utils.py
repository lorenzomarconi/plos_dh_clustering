from typing import Final
from _utils import COLOR

PLOTS_DIR: Final = 'plots_output'
A1C_LABEL: Final = "HbA1c"

def get_plot_filepath(filename) :
	return f"./{ PLOTS_DIR }/{ filename }"

cluster_ordering = [
	'controlled',
	'moderately controlled',
	'uncontrolled wci',
	'uncontrolled'
]

cluster_colors = {
	'controlled': 'black',
	'moderately controlled': 'black',
	'uncontrolled wci': 'black',
	'uncontrolled': 'black',
} if COLOR == 'bw' else {
    'controlled': "#198120",
    'moderately controlled': '#FDD835',
    'uncontrolled wci': '#FB8C00',
    'uncontrolled': '#B71C1C',
}

cluster_markers = {
    'controlled':            '^', 	
    'moderately controlled': '*', 	
    'uncontrolled wci':      'o', 	
    'uncontrolled':          's',
}

cluster_linestyles = {
    'controlled':            '-', 	
    'moderately controlled': '--', 	
    'uncontrolled wci':      '-.', 	
    'uncontrolled':          ':',
}

cluster_multiline_labels = {
	'controlled': "controlled",
	'moderately controlled': "moderately" + "\n" + "controlled",
	'uncontrolled wci': "uncontrolled" + "\n" + "wci",
	'uncontrolled': "uncontrolled"
}

cluster_inline_labels = {
	'controlled': 'controlled',
	'moderately controlled': 'moderately controlled',
	'uncontrolled wci': 'uncontrolled wci',
	'uncontrolled': 'uncontrolled',
}

def check_dataframe_column(df, column_name) :
	if column_name not in df.columns :
		raise ValueError(f"DataFrame must contain '{ column_name }' column.")

def check_dataframe_columns(df, columns_list) :
	for column_name in columns_list :
		check_dataframe_column(df, column_name)
