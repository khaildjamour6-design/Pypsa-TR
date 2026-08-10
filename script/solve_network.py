"""
solve_network.py — Stage 7

Solves the linear optimal dispatch problem for the assembled PyPSA-Turkey
network (Stage 6 output) using the HiGHS solver, per the solver setting
in configs/default.yaml (switched from Gurobi to HiGHS per Path 1
config corrections for WSL2 stability / open-source licensing).

Output: results/networks/turkey_solved.nc
        results/summary.csv  (capacity, generation, cost, LCOE by carrier)
"""

import sys
from pathlib import Path

import pandas as pd
import pypsa


def solve_network(input_path: str, output_path: str, summary_path: str, solver: str = "highs"):
    n = pypsa.Network(input_path)

    # =========================================================================
    # GLOBAL CONSTRAINTS & OPERATIONAL LIMITS (TEİAŞ CALIBRATION)
    # =========================================================================

    # 1. Cap annual conventional hydro generation at 65 TWh (65,000,000 MWh)
    # Prevents zero-marginal-cost hydro from acting as infinite 100% capacity baseload
    if "hydro" in n.generators.carrier.values or (hasattr(n, "storage_units") and "hydro" in n.storage_units.carrier.values):
        if "hydro_annual_limit" not in n.global_constraints.index:
            n.add(
                "GlobalConstraint",
                "hydro_annual_limit",
                carrier_attribute="hydro",
                sense="<=",
                constant=65e6,  # 65 TWh in MWh
                type="operational_limit",
            )

    # 2. Add operational minimum limit for CCGT / Gas generation (35 TWh/year)
    # Forces natural gas to stay active for dynamic grid reserves and ramping
    if "CCGT" in n.generators.carrier.values or "gas" in n.generators.carrier.values:
        gas_carrier = "CCGT" if "CCGT" in n.generators.carrier.values else "gas"
        if "gas_annual_minimum" not in n.global_constraints.index:
            n.add(
                "GlobalConstraint",
                "gas_annual_minimum",
                carrier_attribute=gas_carrier,
                sense=">=",
                constant=35e6,  # 35 TWh in MWh
                type="operational_limit",
            )

    # =========================================================================
    # OPTIMIZATION
    # =========================================================================
    status, condition = n.optimize(solver_name=solver)
    if status != "ok":
        raise RuntimeError(f"solve did not converge: status={status}, condition={condition}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(output_path)

    # Summarize generation across carriers
    gen_by_carrier_mwh = (
        n.generators_t.p.T.groupby(n.generators.carrier).sum().T.multiply(n.snapshot_weightings.generators, axis=0).sum()
    )
    
    # Check if storage units generated power and add them to summary
    if hasattr(n, "storage_units") and not n.storage_units.empty and not n.storage_units_t.p.empty:
        storage_mwh = (
            n.storage_units_t.p.clip(lower=0)
            .T.groupby(n.storage_units.carrier)
            .sum()
            .T.multiply(n.snapshot_weightings.generators, axis=0)
            .sum()
        )
        gen_by_carrier_mwh = gen_by_carrier_mwh.add(storage_mwh, fill_value=0)

    cap_by_carrier_mw = n.generators.groupby("carrier").p_nom.sum()
    cost_by_carrier_eur = (
        n.generators_t.p.multiply(n.generators.marginal_cost, axis=1)
        .multiply(n.snapshot_weightings.generators, axis=0)
        .T.groupby(n.generators.carrier)
        .sum()
        .T.sum()
    )

    summary = pd.DataFrame(
        {
            "installed_capacity_mw": cap_by_carrier_mw,
            "generation_mwh": gen_by_carrier_mwh,
            "variable_cost_eur": cost_by_carrier_eur,
        }
    ).fillna(0)
    summary["lcoe_eur_per_mwh"] = (
        summary["variable_cost_eur"] / summary["generation_mwh"].replace(0, pd.NA)
    )

    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path)

    total_gen_twh = gen_by_carrier_mwh.sum() / 1e6
    total_cost_meur = cost_by_carrier_eur.sum() / 1e6
    system_avg_cost = cost_by_carrier_eur.sum() / gen_by_carrier_mwh.sum()

    print(
        f"[solve_network] solve status: {status} / {condition}\n"
        f"[solve_network] total generation = {total_gen_twh:.1f} TWh\n"
        f"[solve_network] total variable cost = {total_cost_meur:.1f} M EUR\n"
        f"[solve_network] system average variable cost = {system_avg_cost:.1f} EUR/MWh\n"
        f"[solve_network] wrote {output_path}, {summary_path}"
    )
    return n, summary


if __name__ == "__main__":
    try:
        input_path = snakemake.input[0]  # noqa: F821
        output_path = snakemake.output.network  # noqa: F821
        summary_path = snakemake.output.summary  # noqa: F821
        solver = snakemake.config.get("solving", {}).get("solver", "highs")  # noqa: F821
    except NameError:
        args = sys.argv[1:]
        defaults = [
            "resources/networks/turkey_base.nc",
            "results/networks/turkey_solved.nc",
            "results/summary.csv",
        ]
        args = args + defaults[len(args):]
        input_path, output_path, summary_path = args
        solver = "highs"

    solve_network(input_path, output_path, summary_path, solver)