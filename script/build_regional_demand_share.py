"""
build_regional_demand_share.py — Stage 4b

Computes each region's share of national demand from real population
and GDP data (resources/shaps/turkey_7regions.geojson), using the same
0.6*GDP + 0.4*population weighting used when the 7 regions were built.

Replaces the hardcoded REGIONAL_DEMAND_SHARE placeholder previously in
build_network.py.

Output (resources/regional_demand_share.csv):
    region | share
    Marmara | 0.323
    ...
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

GDP_WEIGHT = 0.6
POP_WEIGHT = 0.4

# turkey_7regions.geojson uses English region names (same convention as
# the atlite renewable CF output); buses.csv / rest of the pipeline use
# Turkish names. Bridge with the same mapping used in build_turkey_weather.py.
REGION_NAME_MAP = {
    "Marmara": "Marmara",
    "Aegean": "Ege",
    "Mediterranean": "Akdeniz",
    "Central_Anatolia": "İç Anadolu",
    "Black_Sea": "Karadeniz",
    "Eastern_Anatolia": "Doğu Anadolu",
    "Southeastern_Anatolia": "Güneydoğu Anadolu",
}


def build_regional_demand_share(regions_path: str, output_path: str) -> pd.DataFrame:
    regions = gpd.read_file(regions_path)[["region", "pop", "gdp"]].copy()

    regions["region"] = regions["region"].map(REGION_NAME_MAP)
    if regions["region"].isna().any():
        raise ValueError("unmapped region name(s) found — check REGION_NAME_MAP")

    pop_share = regions["pop"] / regions["pop"].sum()
    gdp_share = regions["gdp"] / regions["gdp"].sum()
    regions["share"] = GDP_WEIGHT * gdp_share + POP_WEIGHT * pop_share

    total = regions["share"].sum()
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"regional shares do not sum to 1.0 (got {total})")

    out = regions[["region", "share"]].sort_values("region").reset_index(drop=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(
        f"[build_regional_demand_share] wrote {len(out)} regions to {output_path}\n"
        f"{out.to_string(index=False)}"
    )
    return out


if __name__ == "__main__":
    try:
        regions_path = snakemake.input.regions  # noqa: F821
        output_path = snakemake.output[0]  # noqa: F821
    except NameError:
        regions_path = sys.argv[1] if len(sys.argv) > 1 else "resources/shaps/turkey_7regions.geojson"
        output_path = sys.argv[2] if len(sys.argv) > 2 else "resources/regional_demand_share.csv"

    build_regional_demand_share(regions_path, output_path)