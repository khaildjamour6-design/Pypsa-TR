# build_weather.smk — Stage 5
# Builds per-region renewable capacity factor profiles.
#
# Uses real ERA5-derived hourly capacity factor profiles from atlite,
# reshaped from resources/renewables/{solar,wind}_cf_by_region.csv
# (wide format, per-region columns) into the long-format schema
# (snapshot | region | solar_cf | wind_cf) expected by Stage 6.
rule build_weather:
    input:
        solar="resources/renewables/solar_cf_by_region.csv",
        wind="resources/renewables/wind_cf_by_region.csv"
    output:
        "resources/renewable_profiles.csv"
    script:
        "../scripts/build_turkey_weather.py"