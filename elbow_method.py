import clustering
import csv
import numpy as np
import os
import matplotlib.pyplot as plt
from _utils import get_data_filepath
from plots._utils import get_plot_filepath

def run(cohort, min_k, max_k, stored_inertia_filepath = None, use_stored_inertia = False) :
    """
    Computes and plots the elbow method.

    Parameters:
        param min_k : int
            Minimum value for the number of clusters k.
        max_k : int
            Maximum value for the number of clusters k.

    Returns:
        list
            Values of inertia for each k between min_k and max_k.
    """
    
    k2inertia = dict()

    assert not (stored_inertia_filepath is None and use_stored_inertia)
    if use_stored_inertia and os.path.exists(stored_inertia_filepath) :
        with open(stored_inertia_filepath, 'r', newline='') as file :
            reader = csv.reader(file)
            for row in reader:
                k2inertia[int(row[0])] = float(row[1])

    for k in range(min_k, max_k + 1):
        print(f"# clusters: {k}")

        if k not in k2inertia :
            _, inertia = clustering.compute_clusters_for_cohort(k, cohort, random_state=0)
            
            k2inertia[k] = inertia
            if stored_inertia_filepath is not None :
                with open(stored_inertia_filepath, 'a', newline='') as file :
                    writer = csv.writer(file)
                    writer.writerow([k, inertia])

    x = np.arange(min_k, max_k + 1)
    y = [k2inertia[y] for y in sorted(k2inertia.keys())]
    plt.plot(x, y, marker="o")
    plt.xticks(x)
    plt.xlabel("k")
    plt.ylabel("inertia")
    plt.title(f"Elbow method ({ cohort })")
	
	# Save the plot as an SVG file
    svg_filepath = get_plot_filepath(f'elbow_method.svg')
    plt.savefig(svg_filepath, format='svg', bbox_inches='tight')

def run_default() :
    for cohort in ['NC', 'CC'] :
        return run(cohort, 1, 16, get_data_filepath('elbow_method.csv'), True)

if __name__ == '__main__':
    run_default()