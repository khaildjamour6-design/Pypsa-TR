# build_regional_demand_share.smk — Stage 4b
# Computes each region's share of national demand from real
# population/GDP data (0.6*GDP + 0.4*population), replacing the
# previous hardcoded REGIONAL_DEMAND_SHARE placeholder.
rule build_regional_demand_share:
    input:
        regions="resources/shaps/turkey_7regions.geojson"
    output:
        "resources/regional_demand_share.csv"
    script:
        "../scripts/build_regional_demand_share.py"
