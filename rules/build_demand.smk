# build_demand.smk — Stage 2
# Builds the national hourly demand profile from EPIAS load data.
#
# Expects data/raw/{demand_raw_file} (set in configs/turkey.yaml).
# Until the real EPIAS export is added, this points at a synthetic
# placeholder (epias_load.SYNTHETIC.csv) with the same column structure,
# so the full pipeline is runnable end-to-end today.

rule build_demand:
    input:
        raw="data/raw/" + config["data_sources"]["demand_raw_file"]
    output:
        "resources/demand_profiles.csv"
    script:
        "../scripts/build_turkey_demand.py"
