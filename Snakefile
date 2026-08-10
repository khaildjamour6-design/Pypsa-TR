# PyPSA-Turkey
# Snakefile — workflow entry point
#
# Stage 1 skeleton. Rule modules are included below as they are implemented
# (Stage 2 onward). Until then this file only wires up configuration.
#
# Design note (see project roadmap):
#   - Turkey-specific data-processing rules (demand, powerplants) are written
#     from scratch as independent modules.
#   - Generic infrastructure rules (grid extraction from OSM, weather/atlite
#     cutouts, clustering, solving) may reuse PyPSA-Earth's proven rule
#     definitions via `include:` rather than being rewritten — this keeps the
#     model reliable while remaining a "PyPSA-Turkey" project, not a fork.

configfile: "configs/default.yaml"
configfile: "configs/turkey.yaml"


# --- Rule modules -----------------------------------------------------
# Uncomment / add as each stage is implemented and verified.

include: "rules/build_powerplants.smk" # Stage 3 — active
include: "rules/build_demand.smk"        # Stage 2 — active
include: "rules/build_grid.smk"        # Stage 4 — active
include: "rules/build_regional_demand_share.smk"     # Stage 4b — active
include: "rules/build_weather.smk"     # Stage 5 — active
include: "rules/build_network.smk"     # Stage 6 — active
include: "rules/solve_network.smk"     # Stage 7 — active
include: "rules/make_figures.smk"      # Stage 8 — active


rule all:
    input:
        "results/networks/turkey_solved.nc",
        "results/summary.csv",
        "results/figures/installed_capacity.png",
        "results/figures/generation_mix.png",
        "results/figures/dispatch_stack_winter_week.png",
        "results/figures/variable_cost_by_carrier.png",


rule clean:
    shell:
        "rm -rf resources/* results/* .snakemake/log/*"
