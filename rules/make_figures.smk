# make_figures.smk — Stage 8
# Generates summary figures from the solved network.

rule make_figures:
    input:
        network="results/networks/turkey_solved.nc",
        summary="results/summary.csv"
    output:
        "results/figures/installed_capacity.png",
        "results/figures/generation_mix.png",
        "results/figures/dispatch_stack_winter_week.png",
        "results/figures/variable_cost_by_carrier.png"
    script:
        "../scripts/make_figures.py"
