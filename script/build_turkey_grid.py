"""
build_turkey_grid.py — Stage 4

Builds a simplified regional transmission topology for Turkey, following
the PyPSA-GB architectural pattern (one bus per region rather than a
full nodal network — appropriate for national-scale capacity-expansion
studies; a full nodal model would use PyPSA-Earth's OSM-based line
extraction instead).

Regions correspond to Turkey's 7 geographic regions (Marmara, Ege,
Akdeniz, İç Anadolu, Karadeniz, Doğu Anadolu, Güneydoğu Anadolu), matching
the region labels used in build_turkey_powerplants.py (Stage 3).

Expected raw inputs:
    data/raw/teias_buses.csv
        region | lat | lon
    data/raw/teias_lines.csv
        from_region | to_region | capacity_mw | length_km

Output:
    resources/buses.csv   — region, x (lon), y (lat)
    resources/lines.csv   — name, bus0, bus1, s_nom_mw, length_km
"""

import sys
from pathlib import Path

import pandas as pd


def load_buses(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"region", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"buses file missing columns: {missing}")
    return df.rename(columns={"lon": "x", "lat": "y"})


def load_lines(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"from_region", "to_region", "capacity_mw", "length_km"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"lines file missing columns: {missing}")
    return df


def validate(buses: pd.DataFrame, lines: pd.DataFrame) -> None:
    if buses["region"].duplicated().any():
        raise ValueError("duplicate region names in buses file")

    # Turkey's approximate bounding box — catches lat/lon swaps or bad units.
    if not buses["y"].between(35.5, 42.5).all():
        raise ValueError("bus latitude values fall outside Turkey's bounding box")
    if not buses["x"].between(25.5, 45.0).all():
        raise ValueError("bus longitude values fall outside Turkey's bounding box")

    known_regions = set(buses["region"])
    line_regions = set(lines["from_region"]) | set(lines["to_region"])
    unknown = line_regions - known_regions
    if unknown:
        raise ValueError(f"lines reference undefined regions: {unknown}")

    if (lines["capacity_mw"] <= 0).any():
        raise ValueError("non-positive line capacity found")


def build_grid(buses_input: str, lines_input: str, buses_output: str, lines_output: str):
    buses = load_buses(buses_input)
    lines_raw = load_lines(lines_input)
    validate(buses, lines_raw)

    lines = pd.DataFrame(
        {
            "name": [f"{r.from_region}-{r.to_region}" for r in lines_raw.itertuples()],
            "bus0": lines_raw["from_region"],
            "bus1": lines_raw["to_region"],
            "s_nom_mw": lines_raw["capacity_mw"],
            "length_km": lines_raw["length_km"],
        }
    )

    Path(buses_output).parent.mkdir(parents=True, exist_ok=True)
    buses[["region", "x", "y"]].to_csv(buses_output, index=False)
    lines.to_csv(lines_output, index=False)

    print(
        f"[build_turkey_grid] wrote {len(buses)} buses to {buses_output}\n"
        f"[build_turkey_grid] wrote {len(lines)} lines to {lines_output}\n"
        f"[build_turkey_grid] total interconnection capacity = "
        f"{lines['s_nom_mw'].sum():,.0f} MW"
    )
    return buses, lines


if __name__ == "__main__":
    try:
        buses_input = snakemake.input.buses  # noqa: F821
        lines_input = snakemake.input.lines  # noqa: F821
        buses_output = snakemake.output.buses  # noqa: F821
        lines_output = snakemake.output.lines  # noqa: F821
    except NameError:
        buses_input = sys.argv[1] if len(sys.argv) > 1 else "data/raw/teias_buses.csv"
        lines_input = sys.argv[2] if len(sys.argv) > 2 else "data/raw/teias_lines.csv"
        buses_output = sys.argv[3] if len(sys.argv) > 3 else "resources/buses.csv"
        lines_output = sys.argv[4] if len(sys.argv) > 4 else "resources/lines.csv"

    build_grid(buses_input, lines_input, buses_output, lines_output)
