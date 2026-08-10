"""
build_turkey_weather.py — Stage 5

Produces hourly per-region capacity factor profiles for solar PV and
wind, used by Stage 6 to set p_max_pu on renewable generators.

Reads real ERA5-derived hourly capacity factor profiles from atlite
(resources/renewables/solar_cf_by_region.csv, wind_cf_by_region.csv —
wide format, snapshot index x 7 English-named region columns) and
reshapes them into the long-format schema Stage 6 expects, written to
resources/renewable_profiles.csv.

Output (resources/renewable_profiles.csv):
    snapshot | region | solar_cf | wind_cf
"""

import sys
from pathlib import Path

import pandas as pd

# atlite's English region column names -> Turkish region names used in
# resources/buses.csv (confirmed via buses.csv region column, 2026-07-25).
REGION_NAME_MAP = {
    "Marmara": "Marmara",
    "Aegean": "Ege",
    "Mediterranean": "Akdeniz",
    "Central_Anatolia": "İç Anadolu",
    "Black_Sea": "Karadeniz",
    "Eastern_Anatolia": "Doğu Anadolu",
    "Southeastern_Anatolia": "Güneydoğu Anadolu",
}


def build_weather(solar_path: str, wind_path: str, output_path: str) -> pd.DataFrame:
    solar = pd.read_csv(solar_path, index_col=0, parse_dates=True)
    wind = pd.read_csv(wind_path, index_col=0, parse_dates=True)

    solar = solar.rename(columns=REGION_NAME_MAP)
    wind = wind.rename(columns=REGION_NAME_MAP)

    missing_solar = set(REGION_NAME_MAP.values()) - set(solar.columns)
    missing_wind = set(REGION_NAME_MAP.values()) - set(wind.columns)
    if missing_solar or missing_wind:
        raise ValueError(
            f"missing region columns after mapping — solar: {missing_solar}, wind: {missing_wind}"
        )
    if not solar.index.equals(wind.index):
        raise ValueError("solar/wind timestamps do not match")

    solar_long = (
        solar.rename_axis("snapshot")
        .reset_index()
        .melt(id_vars="snapshot", var_name="region", value_name="solar_cf")
    )
    wind_long = (
        wind.rename_axis("snapshot")
        .reset_index()
        .melt(id_vars="snapshot", var_name="region", value_name="wind_cf")
    )

    out = solar_long.merge(wind_long, on=["snapshot", "region"], how="inner")

    if len(out) != len(solar_long):
        raise ValueError("row count changed during merge — snapshot/region mismatch between solar and wind")
    if not out["solar_cf"].between(0, 1).all() or not out["wind_cf"].between(0, 1).all():
        raise ValueError("capacity factors out of [0, 1] range")
    if out[["solar_cf", "wind_cf"]].isna().any().any():
        raise ValueError("NaNs found in capacity factor data")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    mean_solar = out.groupby("region")["solar_cf"].mean().round(3)
    mean_wind = out.groupby("region")["wind_cf"].mean().round(3)
    print(
        f"[build_turkey_weather] wrote {len(out)} rows to {output_path}\n"
        f"[build_turkey_weather] mean solar CF by region:\n{mean_solar.to_string()}\n"
        f"[build_turkey_weather] mean wind CF by region:\n{mean_wind.to_string()}"
    )
    return out


if __name__ == "__main__":
    try:
        solar_path = snakemake.input.solar  # noqa: F821
        wind_path = snakemake.input.wind  # noqa: F821
        output_path = snakemake.output[0]  # noqa: F821
    except NameError:
        solar_path = sys.argv[1] if len(sys.argv) > 1 else "resources/renewables/solar_cf_by_region.csv"
        wind_path = sys.argv[2] if len(sys.argv) > 2 else "resources/renewables/wind_cf_by_region.csv"
        output_path = sys.argv[3] if len(sys.argv) > 3 else "resources/renewable_profiles.csv"

    build_weather(solar_path, wind_path, output_path)