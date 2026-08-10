"""
build_network.py — Stage 6

Assembles a PyPSA Network object for Turkey dynamically configured by turkey.yaml.

Features & Fixes:
  - Single-Pass Hydro Routing: Reservoir hydro at designated buses becomes StorageUnits;
    hydro elsewhere is retained as Run-of-River (RoR) generators to prevent dropping capacity.
  - Transmission Expansion Planning (TEP) on inter-regional links.
  - Battery Energy Storage Systems (BESS) expansion (Store + Charger/Discharger links).
  - Snapshot resolution downsampling support for memory management.
"""

import sys
from pathlib import Path
import pandas as pd
import pypsa
import yaml


def load_config(config_path: str = "config/turkey.yaml") -> dict:
    candidates = [
        Path(config_path),
        Path("configs/turkey.yaml"),
        Path("configs/default.yaml"),
        Path("config/turkey.yaml"),
        Path("turkey.yaml"),
    ]
    
    selected_path = None
    for p in candidates:
        if p.is_file():
            selected_path = p
            break

    if selected_path is None:
        raise FileNotFoundError(
            f"Could not find configuration file in any of these locations: {[str(c) for c in candidates]}"
        )

    print(f"[build_network] Using config file: {selected_path}")
    with open(selected_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_network(
    demand_path: str,
    powerplants_path: str,
    buses_path: str,
    lines_path: str,
    renewables_path: str,
    regional_demand_share_path: str,
    output_path: str,
    config_path: str = "configs/turkey.yaml",
) -> pypsa.Network:

    config = load_config(config_path)

    # 1. Parse Active Scenario Settings
    active_mode_name = config.get("scenario", {}).get("active", "shura_2030")
    active_scenario = config.get("scenario", {}).get("modes", {}).get(active_mode_name, {})

    is_extendable = active_scenario.get("extendable", True)
    co2_limit_mt = active_scenario.get("co2_limit_mt", 140.0)
    resolution_hours = config.get("scenario", {}).get("snapshot_resolution_hours", 1)

    # 2. Extract Hydro & Tech Configuration
    hydro_cfg = config.get("hydro", {})
    ror_flat_cf = hydro_cfg.get("ror", {}).get("flat_capacity_factor", 0.45)
    config_reservoir_buses = set(hydro_cfg.get("reservoir", {}).get("buses", ["TR_SAN", "TR_EAN", "TR_MED"]))
    
    tech_data = config.get("extendable_technologies", {}).get("costs", {})
    co2_factors_fixed = {
        "coal": 0.90, "lignite": 1.10, "oil": 0.65, "gas": 0.40, "CCGT": 0.40,
        "nuclear": 0.0, "hydro": 0.0, "geothermal": 0.0, "biomass": 0.0, "ror": 0.0,
    }

    # Load input datasets
    demand = pd.read_csv(demand_path, parse_dates=["snapshot"])
    plants = pd.read_csv(powerplants_path)
    buses = pd.read_csv(buses_path)
    lines = pd.read_csv(lines_path)
    renewables = pd.read_csv(renewables_path, parse_dates=["snapshot"])
    regional_demand_share = pd.read_csv(regional_demand_share_path).set_index("region")["share"]

    # Validate reservoir buses against actual regional buses present in dataset
    valid_buses = set(buses["region"].unique())
    reservoir_buses = config_reservoir_buses.intersection(valid_buses)

    if resolution_hours > 1:
        keep_snapshots = demand["snapshot"].iloc[::resolution_hours].values
        demand = demand[demand["snapshot"].isin(keep_snapshots)].reset_index(drop=True)
        renewables = renewables[renewables["snapshot"].isin(keep_snapshots)].reset_index(drop=True)

    n = pypsa.Network()
    n.set_snapshots(demand["snapshot"].values)
    n.snapshot_weightings.loc[:, :] = resolution_hours

    # Add Carriers
    extendable_carriers = config.get("extendable_technologies", {}).get("carriers", ["solar", "wind", "gas"])
    all_carriers = set(plants["carrier"]) | {"AC", "Li-ion", "hydro_reservoir", "ror"} | set(extendable_carriers)
    for carrier in sorted(all_carriers):
        if carrier not in n.carriers.index:
            co2 = tech_data.get(carrier, {}).get("co2_t_per_mwh", co2_factors_fixed.get(carrier, 0.0))
            n.add("Carrier", carrier, co2_emissions=co2)

    # Global CO2 Limit Constraint
    if co2_limit_mt is not None:
        n.add(
            "GlobalConstraint",
            "co2_limit",
            type="co2_limit",
            carrier_attribute="co2_emissions",
            sense="<=",
            constant=co2_limit_mt * 1e6,
        )

    # Add Buses
    for row in buses.itertuples():
        n.add("Bus", row.region, x=row.x, y=row.y, carrier="AC")

    # Add Inter-Regional Links (With optional Transmission Expansion Planning)
    line_expansion = is_extendable and config.get("transmission", {}).get("extendable", False)
    line_cost_per_mw = config.get("transmission", {}).get("capital_cost_eur_per_mw", 400.0)

    for row in lines.itertuples():
        n.add(
            "Link",
            row.name,
            bus0=row.bus0,
            bus1=row.bus1,
            p_nom=row.s_nom_mw,
            p_nom_extendable=line_expansion,
            capital_cost=line_cost_per_mw if line_expansion else 0.0,
            p_min_pu=-1,
            efficiency=1.0,
            marginal_cost=0.0,
        )

    # Add Loads
    national_load = demand.set_index("snapshot")["load_mw"]
    for region, share in regional_demand_share.items():
        n.add("Load", f"load_{region}", bus=region, p_set=(national_load * share).values)

    renew_pivot_solar = renewables.pivot(index="snapshot", columns="region", values="solar_cf")
    renew_pivot_wind = renewables.pivot(index="snapshot", columns="region", values="wind_cf")

    # Add Existing Generators (Single-Pass Hydro Routing)
    for row in plants.itertuples():
        carrier = row.carrier
        
        # Hydro Routing Logic
        if carrier in ["hydro", "hydro_reservoir"]:
            if row.region in reservoir_buses:
                # Skip here: Aggregated cleanly into StorageUnit below
                continue
            else:
                # Retain hydro outside reservoir buses as Run-of-River (prevents dropped capacity)
                carrier = "ror"
                p_max_pu = ror_flat_cf
        elif carrier == "solar":
            p_max_pu = renew_pivot_solar[row.region].values
        elif carrier == "wind":
            p_max_pu = renew_pivot_wind[row.region].values
        elif carrier == "ror":
            p_max_pu = ror_flat_cf
        else:
            p_max_pu = 1.0

        n.add(
            "Generator",
            row.name,
            bus=row.region,
            carrier=carrier,
            p_nom=row.p_nom_mw,
            marginal_cost=getattr(row, "marginal_cost_eur_per_mwh", 0.0 if carrier == "ror" else 30.0),
            p_max_pu=p_max_pu,
        )

    # Add Extendable Generators & Battery Storage (Layer D)
    if is_extendable:
        for region in buses["region"]:
            # 1. Renewable & Thermal Expansion
            for carrier in extendable_carriers:
                tech = tech_data.get(carrier, {})
                if carrier == "solar":
                    p_max_pu = renew_pivot_solar[region].values
                elif carrier == "wind":
                    p_max_pu = renew_pivot_wind[region].values
                else:
                    p_max_pu = 1.0

                p_nom_max = tech.get("p_nom_max_mw")
                
                n.add(
                    "Generator",
                    f"new_{carrier}_{region}",
                    bus=region,
                    carrier=carrier,
                    p_nom=0,
                    p_nom_extendable=True,
                    p_nom_max=p_nom_max if p_nom_max is not None else float("inf"),
                    capital_cost=tech.get("capital_cost_eur_per_kw", 0.0) * 1000,
                    marginal_cost=30.0 if carrier == "gas" else 0.0,
                    p_max_pu=p_max_pu,
                )

            # 2. Battery Energy Storage System (BESS) Expansion
            bess_cfg = config.get("battery", {})
            if bess_cfg.get("extendable", True):
                n.add("Bus", f"{region}_battery", carrier="Li-ion")
                n.add(
                    "Store",
                    f"{region}_battery_store",
                    bus=f"{region}_battery",
                    carrier="Li-ion",
                    e_nom_extendable=True,
                    capital_cost=bess_cfg.get("capital_cost_eur_per_kwh", 150.0) * 1000,
                    standing_loss=0.0001,
                )
                n.add(
                    "Link",
                    f"{region}_battery_charger",
                    bus0=region,
                    bus1=f"{region}_battery",
                    p_nom_extendable=True,
                    efficiency=bess_cfg.get("efficiency_charge", 0.92),
                    capital_cost=bess_cfg.get("capital_cost_eur_per_kw", 100.0) * 1000,
                )
                n.add(
                    "Link",
                    f"{region}_battery_discharger",
                    bus0=f"{region}_battery",
                    bus1=region,
                    p_nom_extendable=True,
                    efficiency=bess_cfg.get("efficiency_discharge", 0.92),
                )

    # Layer C: Reservoir Hydro Dynamics (Only at designated reservoir buses)
    hydro_df = plants[plants["carrier"].isin(["hydro", "hydro_reservoir"])] if "carrier" in plants.columns else pd.DataFrame()

    for bus in reservoir_buses:
        bus_hydro = hydro_df[hydro_df["region"] == bus] if not hydro_df.empty else pd.DataFrame()
        total_p_nom = bus_hydro["p_nom_mw"].sum() if not bus_hydro.empty else 0.0

        if total_p_nom > 0:
            n.add(
                "StorageUnit",
                name=f"{bus}_hydro_reservoir",
                bus=bus,
                carrier="hydro_reservoir",
                p_nom=total_p_nom,
                max_hours=hydro_cfg.get("reservoir", {}).get("max_hours", 1200),
                cyclic_state_of_charge=True,
                efficiency_dispatch=hydro_cfg.get("reservoir", {}).get("efficiency_dispatch", 0.90),
                marginal_cost=0.0,
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(output_path)

    print(
        f"[build_network] assembled network ({active_mode_name}): {len(n.buses)} buses, "
        f"{len(n.links)} links, {len(n.generators)} generators, {len(n.stores)} stores, "
        f"{len(n.loads)} loads, {len(n.snapshots)} snapshots\n"
        f"[build_network] extendable mode = {is_extendable}, transmission expansion = {line_expansion}\n"
        f"[build_network] reservoir hydro buses = {sorted(list(reservoir_buses))}\n"
        f"[build_network] wrote {output_path}"
    )
    return n


if __name__ == "__main__":
    defaults = [
        "resources/demand_profiles.csv",
        "resources/powerplants.csv",
        "resources/buses.csv",
        "resources/lines.csv",
        "resources/renewable_profiles.csv",
        "resources/regional_demand_share.csv",
        "resources/networks/turkey_base.nc",
        "configs/turkey.yaml",
    ]
    args = sys.argv[1:] + defaults[len(sys.argv[1:]):]
    build_network(*args[:7], config_path=args[7])
