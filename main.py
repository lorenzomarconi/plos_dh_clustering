import initial_cohort_count
import cohorts
import clustering
import elbow_method
import nephropathy
import retinopathy
import plots

def run() :
    # 1) Computing clusters
    initial_cohort_count.run()
    cohorts.compute_cohorts()
    elbow_method.run_default()
    clustering.compute_clusters()

    # 2) Intermediate step: evaluate HbA1c trends and manually assign a lable to clusters
    plots.plot_hba1c_trends()

    # 3) Materialize clusters and establish comorbidities
    clustering.materialize_clusters()
    nephropathy.get_nephropathic_patients()
    retinopathy.get_retinopathic_patients()
    nephropathy.materialize_nephropathy_conditions()
    retinopathy.materialize_retinopathy_conditions()
    
    # 4) Plot statistics
    plots.plot_age_boxplots()
    plots.plot_bmi_boxplots()
    plots.plot_sex_histograms()
    plots.plot_insulin_cumulative_incidences()
    plots.plot_comorbidities_cumulative_incidences()
    plots.plot_num_prescriptions_boxplots()
    plots.plot_num_hba1c_boxplots()

if __name__ == '__main__':
    run()