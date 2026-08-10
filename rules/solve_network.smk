# solve_network.smk — Stage 7
# Solves the optimization (HiGHS solver, per configs/default.yaml).

rule solve_network:
    input:
        "resources/networks/turkey_base.nc"
    output:
        network="results/networks/turkey_solved.nc",
        summary="results/summary.csv"
    script:
        "../scripts/solve_network.py"
