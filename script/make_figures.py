"""
make_figures.py — Stage 8

Generates summary figures from a solved network (Stage 7 output):
installed capacity by carrier, generation mix, a representative winter
dispatch week, and variable cost by carrier.

Run manually after `snakemake` completes:
    python scripts/make_figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pypsa

CARRIER_COLORS = {
    "hydro": "#2166ac", "ror": "#67a9cf", "wind": "#4daf4a", "solar": "#ffcc00",
    "gas": "#e78ac3", "coal": "#5c4033", "lignite": "#8b4513",
    "geothermal": "#b35806", "biomass": "#66c2a5", "oil": "#525252", "nuclear": "#984ea3",
}


def make_figures(
    network_path: str = "results/networks/turkey_solved.nc",
    summary_path: str = "results/summary.csv",
    output_dir: str = "results/figures",
    dispatch_week_start: str = "2023-01-09",
    dispatch_week_end: str = "2023-01-15",
):
    plt.rcParams.update({"font.size": 10, "figure.dpi": 150})
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    n = pypsa.Network(network_path)
    summary = pd.read_csv(summary_path, index_col=0)

    # Installed capacity
    fig, ax = plt.subplots(figsize=(7, 4.5))
    cap = summary["installed_capacity_mw"].sort_values(ascending=True) / 1e3
    ax.barh(cap.index, cap.values, color=[CARRIER_COLORS.get(c, "#999999") for c in cap.index])
    ax.set_xlabel("Installed capacity (GW)")
    ax.set_title("PyPSA-Turkey — Installed Capacity by Carrier")
    for i, v in enumerate(cap.values):
        ax.text(v + 0.3, i, f"{v:.1f}", va="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/installed_capacity.png")
    plt.close()

    # Generation mix
    fig, ax = plt.subplots(figsize=(7, 4.5))
    gen = (summary["generation_mwh"] / 1e6).sort_values(ascending=True)
    ax.barh(gen.index, gen.values, color=[CARRIER_COLORS.get(c, "#999999") for c in gen.index])
    ax.set_xlabel("Annual generation (TWh)")
    ax.set_title("PyPSA-Turkey — Generation Mix by Carrier")
    for i, v in enumerate(gen.values):
        ax.text(v + 1, i, f"{v:.1f}", va="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/generation_mix.png")
    plt.close()

    # Dispatch stack, representative week
    gen_t = n.generators_t.p.T.groupby(n.generators.carrier).sum().T
    week = gen_t.loc[dispatch_week_start:dispatch_week_end]
    order = week.mean().sort_values().index.tolist()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.stackplot(week.index, [week[c] for c in order], labels=order,
                 colors=[CARRIER_COLORS.get(c, "#999999") for c in order])
    load_week = n.loads_t.p_set.sum(axis=1).loc[dispatch_week_start:dispatch_week_end]
    ax.plot(load_week.index, load_week.values, color="black", linewidth=1.5, label="Total demand")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_ylabel("MW")
    ax.set_title(f"PyPSA-Turkey — Dispatch Stack, {dispatch_week_start} to {dispatch_week_end}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/dispatch_stack_winter_week.png")
    plt.close()

    # Variable cost by carrier
    fig, ax = plt.subplots(figsize=(7, 4.5))
    lcoe = summary["lcoe_eur_per_mwh"].dropna().sort_values(ascending=True)
    ax.barh(lcoe.index, lcoe.values, color=[CARRIER_COLORS.get(c, "#999999") for c in lcoe.index])
    ax.set_xlabel("Variable cost (EUR/MWh)")
    ax.set_title("PyPSA-Turkey — Variable Generation Cost by Carrier\n(marginal cost only, not full LCOE)")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/variable_cost_by_carrier.png")
    plt.close()

    print(f"[make_figures] wrote 4 figures to {output_dir}/")


if __name__ == "__main__":
    try:
        network_path = snakemake.input.network  # noqa: F821
        summary_path = snakemake.input.summary  # noqa: F821
        output_dir = str(Path(snakemake.output[0]).parent)  # noqa: F821
        make_figures(network_path, summary_path, output_dir)
    except NameError:
        make_figures()
