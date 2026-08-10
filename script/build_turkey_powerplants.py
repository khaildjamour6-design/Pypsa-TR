"""
build_turkey_powerplants.py — Stage 3

Builds the Turkish generation fleet from a TEIAS-format power plant
registry (TEİAŞ publishes installed-capacity-by-plant tables; a
"kurulu güç" / installed capacity export is the expected raw input).

Expected raw input (data/raw/teias_powerplants.csv), columns (Turkish
or English alias, see *_ALIASES below):

    Santral Adı        | Yakıt Tipi | Kurulu Güç (MW) | Bölge
    Afşin-Elbistan A     | Linyit      | 1355             | İç Anadolu
    ...

Fuel-type strings are mapped to a small set of PyPSA-Turkey carriers via
FUEL_MAP; anything unmapped is flagged rather than silently dropped, so
new TEIAS fuel categories don't disappear unnoticed.

Output (resources/powerplants.csv):
    name | carrier | p_nom_mw | region | marginal_cost_eur_per_mwh
"""

import sys
from pathlib import Path

import pandas as pd

NAME_ALIASES = ["Santral Adı", "name", "plant_name"]
FUEL_ALIASES = ["Yakıt Tipi", "fuel", "fuel_type", "carrier"]
CAPACITY_ALIASES = ["Kurulu Güç (MW)", "capacity_mw", "p_nom_mw"]
REGION_ALIASES = ["Bölge", "region"]

# Maps raw TEIAS fuel-type strings (Turkish, as published) to PyPSA
# carrier names + an indicative short-run marginal cost (EUR/MWh) used
# for Stage 6/7 dispatch. Costs are illustrative placeholders — replace
# with project-specific fuel-price assumptions before publishing results.
FUEL_MAP = {
    "Linyit": ("lignite", 28.0),
    "Taşkömürü": ("coal", 32.0),
    "İthal Kömür": ("coal", 32.0),
    "Doğalgaz": ("gas", 55.0),
    "Doğal Gaz": ("gas", 55.0),
    "Barajlı": ("hydro", 0.0),
    "Akarsu": ("ror", 0.0),  # run-of-river
    "Rüzgar": ("wind", 0.0),
    "Güneş": ("solar", 0.0),
    "Jeotermal": ("geothermal", 8.0),
    "Biyokütle": ("biomass", 15.0),
    "Nükleer": ("nuclear", 10.0),
    "Fuel Oil": ("oil", 90.0),
}


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str:
    for name in aliases:
        if name in df.columns:
            return name
    raise KeyError(
        f"None of the expected columns {aliases} found in raw file "
        f"(columns present: {list(df.columns)})."
    )


def load_raw_teias(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    name_col = _find_column(df, NAME_ALIASES)
    fuel_col = _find_column(df, FUEL_ALIASES)
    cap_col = _find_column(df, CAPACITY_ALIASES)
    region_col = _find_column(df, REGION_ALIASES)

    out = pd.DataFrame(
        {
            "name": df[name_col],
            "fuel_raw": df[fuel_col],
            "p_nom_mw": pd.to_numeric(df[cap_col], errors="coerce"),
            "region": df[region_col],
        }
    )
    return out


def map_fuels(df: pd.DataFrame) -> pd.DataFrame:
    unmapped = sorted(set(df["fuel_raw"]) - set(FUEL_MAP))
    if unmapped:
        raise ValueError(
            f"Unrecognized fuel types in raw data: {unmapped}. "
            f"Add them to FUEL_MAP in build_turkey_powerplants.py."
        )
    mapped = df["fuel_raw"].map(FUEL_MAP)
    df = df.copy()
    df["carrier"] = mapped.map(lambda x: x[0])
    df["marginal_cost_eur_per_mwh"] = mapped.map(lambda x: x[1])
    return df.drop(columns=["fuel_raw"])


def validate(df: pd.DataFrame) -> None:
    if df["p_nom_mw"].isna().any():
        bad = df[df["p_nom_mw"].isna()]["name"].tolist()
        raise ValueError(f"missing/unparseable capacity for plants: {bad}")
    if (df["p_nom_mw"] <= 0).any():
        bad = df[df["p_nom_mw"] <= 0]["name"].tolist()
        raise ValueError(f"non-positive capacity for plants: {bad}")
    if df["name"].duplicated().any():
        dupes = df[df["name"].duplicated()]["name"].tolist()
        raise ValueError(f"duplicate plant names: {dupes}")

    total_gw = df["p_nom_mw"].sum() / 1e3
    # Turkey's total installed capacity is roughly 100-115 GW depending on
    # year; loose sanity bound to catch unit errors, not validate accuracy.
    if not (50 < total_gw < 200):
        raise ValueError(
            f"total installed capacity {total_gw:.1f} GW is outside a "
            f"plausible range for Turkey — check units in the raw file"
        )


def build_powerplants(input_path: str, output_path: str) -> pd.DataFrame:
    raw = load_raw_teias(input_path)
    mapped = map_fuels(raw)
    validate(mapped)

    out = mapped[["name", "carrier", "p_nom_mw", "region", "marginal_cost_eur_per_mwh"]]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    by_carrier = out.groupby("carrier")["p_nom_mw"].sum().sort_values(ascending=False)
    total_gw = out["p_nom_mw"].sum() / 1e3
    print(
        f"[build_turkey_powerplants] wrote {len(out)} plants to {output_path}\n"
        f"[build_turkey_powerplants] total installed capacity = {total_gw:.1f} GW\n"
        f"[build_turkey_powerplants] by carrier (MW):\n{by_carrier.to_string()}"
    )
    return out


if __name__ == "__main__":
    try:
        input_path = snakemake.input.raw  # noqa: F821
        output_path = snakemake.output[0]  # noqa: F821
    except NameError:
        input_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/teias_powerplants.csv"
        output_path = sys.argv[2] if len(sys.argv) > 2 else "resources/powerplants.csv"

    build_powerplants(input_path, output_path)
