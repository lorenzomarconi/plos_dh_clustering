"""Command-line entry point for the clustering pipeline.

Examples
--------
Run the full pipeline:

    python main.py

Run only the cohort-building and clustering phases:

    python main.py --steps initial_cohort_count compute_cohorts elbow_method compute_clusters

Run the comorbidity analysis and final plotting phases only:

    python main.py --steps comorbidities final_plots
"""

import argparse

import clustering
import cohorts
import elbow_method
import initial_cohort_count
import nephropathy
import plots
import retinopathy

def step_initial_cohort_count() :
    initial_cohort_count.run()

def step_compute_cohorts() :
    cohorts.compute_cohorts()

def step_elbow_method() :
    elbow_method.run_default()

def step_compute_clusters() :
    clustering.compute_clusters()

def step_plot_hba1c_trends() :
    plots.plot_hba1c_trends()

def step_materialize_clusters() :
    clustering.materialize_clusters()

def step_comorbidities() :
    nephropathy.get_nephropathic_patients()
    retinopathy.get_retinopathic_patients()
    nephropathy.materialize_nephropathy_conditions()
    retinopathy.materialize_retinopathy_conditions()

def step_final_plots() :
    plots.plot_age_boxplots()
    plots.plot_bmi_boxplots()
    plots.plot_sex_histograms()
    plots.plot_insulin_cumulative_incidences()
    plots.plot_comorbidities_cumulative_incidences()
    plots.plot_num_prescriptions_boxplots()
    plots.plot_num_hba1c_boxplots()

STEPS = {
    "initial_cohort_count": step_initial_cohort_count,
    "compute_cohorts":      step_compute_cohorts,
    "elbow_method":         step_elbow_method,
    "compute_clusters":     step_compute_clusters,
    "plot_hba1c_trends":    step_plot_hba1c_trends,
    "materialize_clusters": step_materialize_clusters,
    "comorbidities":        step_comorbidities,
    "final_plots":          step_final_plots
}

def parse_steps(raw_steps) :
    if not raw_steps or raw_steps == ["all"] :
        return list(STEPS)

    chosen = []
    for item in raw_steps :
        chosen.extend(step.strip() for step in item.split(",") if step.strip())

    bad = [step for step in chosen if step not in STEPS]
    if bad :
        valid = ", ".join(STEPS)
        raise SystemExit(
            f"Unknown step(s): {', '.join(sorted(set(bad)))}\n"
            f"Valid steps: {valid}\n"
            f"Use --steps all to run everything."
        )

    seen = set(chosen)
    return [step for step in STEPS if step in seen]

def main() :
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--steps",
        nargs="*",
        default=["all"],
        help="Steps to run, for example: --steps compute_cohorts compute_clusters or --steps all",
    )
    args = parser.parse_args()

    for step in parse_steps(args.steps) :
        STEPS[step]()

if __name__ == "__main__" :
    main()
