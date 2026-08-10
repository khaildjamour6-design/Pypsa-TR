# build_grid.smk — Stage 4
# Builds the simplified 7-region transmission topology from TEIAS grid data.

rule build_grid:
    input:
        buses="data/raw/" + config["data_sources"]["buses_raw_file"],
        lines="data/raw/" + config["data_sources"]["lines_raw_file"]
    output:
        buses="resources/buses.csv",
        lines="resources/lines.csv"
    script:
        "../scripts/build_turkey_grid.py"
