# build_powerplants.smk — Stage 3
# Builds the Turkish generation fleet from TEIAS registry data.

rule build_powerplants:
    input:
        raw="data/raw/" + config["data_sources"]["powerplants_raw_file"]
    output:
        "resources/powerplants.csv"
    script:
        "../scripts/build_turkey_powerplants.py"
