from .age_boxplot import plot_age_boxplots
from .bmi_boxplot import plot_bmi_boxplots
from .sex_histogram import plot_sex_histograms
from .hba1c_trends import plot_hba1c_trends
from .insulin_incidence import plot_insulin_cumulative_incidences
from .comorbidities import plot_comorbidities_cumulative_incidences
from .num_prescriptions_boxplot import plot_num_prescriptions_boxplots
from .num_hba1c_boxplot import plot_num_hba1c_boxplots

# This allows saving text as such (not as an SVG curve)
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype'] = 'none'