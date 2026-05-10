# Longitudinal HbA1c trajectory clustering

This repository contains the code used to build and analyze longitudinal HbA1c-based patient cohorts and to cluster their trajectories with time-series k-means using DTW distance.

## What the pipeline does

The workflow is split into named steps so that one can run the whole pipeline or only the needed part(s).

Available steps are:

- `initial_cohort_count`: Counts the initial eligible cohort.
- `compute_cohorts`: Extracts patients with sufficient HbA1c measurements and builds two cohorts:
   - **CC**: cohort with valid longitudinal HbA1c subsequences.
   - **NC**: subset of CC with a diagnosis date close to the first HbA1c measurements.
- `elbow_method`: Searches for an appropriate number of clusters with the elbow method.
- `compute_clusters` Computes the final clusters.
- `plot_hba1c_trends`: Generates HbA1c trend plots for manual cluster interpretation.
- `materialize_clusters`: Materializes clusters into PostgreSQL tables.
- `comorbidities`: Performs the comorbidity analysis and stores the information into PostgreSQL tables.
- `final_plots`: Produces summary plots for the final analysis.

The steps run in the same order as above.

## Requirements

Install the Python dependencies:

```bash
pip install sqlalchemy
pip install psycopg2-binary
pip install pandas
pip install tslearn
pip install matplotlib
pip install h5py
```

## Configuration

Edit `config.ini` before running the pipeline.

Important settings include:

- `clustering.first_year`
- `clustering.last_year`
- `clustering.clustering_years`
- `clustering.n_clusters`
- `io.data_dir`
- `io.clustering_schema`
- PostgreSQL connection details in the `[database]` section

The code expects the data directory specified in `io.data_dir` to exist or be creatable, and it writes intermediate CSV files there.

## How to run

From the project root, run the full pipeline with:

```bash
python main.py
```

To run only selected steps, pass them with `--steps`:

```bash
python main.py --steps compute_cohorts compute_clusters
```

You can also provide a comma-separated list:

```bash
python main.py --steps compute_cohorts,compute_clusters
```

To run every step explicitly:

```bash
python main.py --steps all
```

## Outputs

Outputs include:

- Intermediate CSV files in the configured data directory
- Cluster CSV files for the `CC` and `NC` cohorts
- Elbow-method results and plots
- Materialized PostgreSQL tables for clusters and comorbidity analyses
- Summary plots for age, BMI, sex, insulin incidence, comorbidities, prescriptions, and HbA1c counts

Some scripts prompt for confirmation before overwriting or appending to existing database tables.
