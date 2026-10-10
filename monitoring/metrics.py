from prometheus_client import Gauge


# Current carbon intensity
carbon_intensity = Gauge(
    "carbon_intensity_gco2_kwh",
    "Current carbon intensity in gCO2/kWh"
)

# ML-predicted carbon intensity
predicted_carbon_intensity = Gauge(
    "predicted_carbon_intensity_gco2_kwh",
    "Predicted carbon intensity in gCO2/kWh"
)

# Workload energy consumption
energy_consumption = Gauge(
    "workload_energy_kwh",
    "Workload energy consumption in kWh"
)

# Workload carbon emissions
carbon_emissions = Gauge(
    "workload_carbon_kg",
    "Workload carbon emissions in kgCO2e"
)

# Scheduling delay
scheduling_delay = Gauge(
    "scheduling_delay_minutes",
    "Scheduling delay in minutes"
)
