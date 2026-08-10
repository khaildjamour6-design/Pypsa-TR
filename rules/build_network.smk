# build_network.smk — Stage 6
# Assembles the full PyPSA network from resources/*.
rule build_network:
    input:
        demand="resources/demand_profiles.csv",
        powerplants="resources/powerplants.csv",
        buses="resources/buses.csv",
        lines="resources/lines.csv",
        renewables="resources/renewable_profiles.csv",
        regional_demand_share="resources/regional_demand_share.csv"
    output:
        "resources/networks/turkey_base.nc"
    script:
        "../scripts/build_network.py"
