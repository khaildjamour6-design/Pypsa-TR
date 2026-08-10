"""
build_turkey_demand.py — Stage 2

Builds an hourly national demand profile for Turkey from EPIAS
("Şeffaflık Platformu" / transparency platform) real-time consumption
data. Written as an independent module rather than a patched copy of
PyPSA-Earth's generic demand script, since EPIAS's export format and
Turkey's demand data structure don't match PyPSA-Earth's assumptions.

Expected raw input (data/raw/epias_load.csv):
    A CSV export from EPIAS's real-time consumption data, either in the
    platform's native Turkish column names or an English equivalent:

        Tarih                | Saat  | Tüketim Miktarı (MWh)
        01.01.2023            | 00:00  | 28345.2
        01.01.2023            | 01:00  | 27110.8
        ...

    or equivalently:

        date       | hour | load_mwh
        2023-01-01  | 0    | 28345.2

    Column-name matching is alias-based (see *_ALIASES below) so a raw
    EPIAS export can be dropped in without renaming columns by hand.

Output (resources/demand_profiles.csv):
    snapshot            | load_mw
    2023-01-01 00:00:00  | 28345.2
    ...

This is a *national single-node* profile (Stage 2 scope). Disaggregation
to individual buses happens in Stage 4/6 once the grid topology exists.
"""

import sys
from pathlib import Path

import pandas as pd

DATE_ALIASES = ["Tarih", "date", "Date", "tarih"]
HOUR_ALIASES = ["Saat", "hour", "Hour", "saat"]
LOAD_ALIASES = [
    "Tüketim Miktarı (MWh)",
    "Tüketim Miktarı(MWh)",   
    "Tüketim (MWh)",
    "Consumption (MWh)",
    "load_mwh",
    "consumption_mwh",
]


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str:
    for name in aliases:
        if name in df.columns:
            return name
    raise KeyError(
        f"None of the expected columns {aliases} found in raw file "
        f"(columns present: {list(df.columns)}). If EPIAS has changed its "
        f"export format, add the new column name to the *_ALIASES list "
        f"at the top of this script."
    )


def _parse_load_values(raw: pd.Series) -> pd.Series:
    """Parse load values, handling both plain decimal ('28345.2') and
    Turkish-formatted ('28.345,20' — '.' thousands, ',' decimal) strings."""
    s = raw.astype(str).str.strip()
    turkish_fmt = s.str.match(r"^\d{1,3}(\.\d{3})*,\d+$")
    s = s.mask(turkish_fmt, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


def load_raw_epias(path: str) -> pd.Series:
    """Read a raw EPIAS-format load CSV and return an hourly MW series
    indexed by timestamp."""
    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")

    date_col = _find_column(df, DATE_ALIASES)
    hour_col = _find_column(df, HOUR_ALIASES)
    load_col = _find_column(df, LOAD_ALIASES)

    dates = pd.to_datetime(df[date_col], dayfirst=True)
    hours = df[hour_col].astype(str).str.extract(r"(\d+)")[0].astype(int)
    timestamps = dates + pd.to_timedelta(hours, unit="h")

    load_mw = _parse_load_values(df[load_col])

    series = pd.Series(load_mw.values, index=pd.DatetimeIndex(timestamps), name="load_mw")
    series = series.sort_index()
    return series


def validate(series: pd.Series) -> None:
    """Sanity checks mirrored in tests/test_demand.py — kept here too so
    a bad raw file fails loudly at build time, not just at test time."""
    if series.isna().any():
        n_missing = int(series.isna().sum())
        raise ValueError(f"{n_missing} missing/unparseable load values in raw data")

    if (series < 0).any():
        raise ValueError("negative demand values found in raw data")

    n = len(series)
    if n not in (8760, 8784):  # 8784 = leap year
        raise ValueError(
            f"expected 8760 or 8784 hourly rows for a full year, got {n}"
        )

    gaps = series.index.to_series().diff().dropna()
    if not (gaps == pd.Timedelta(hours=1)).all():
        bad = gaps[gaps != pd.Timedelta(hours=1)]
        raise ValueError(f"non-hourly gaps found in timeseries at:\n{bad}")


def build_demand(input_path: str, output_path: str) -> pd.DataFrame:
    raw = load_raw_epias(input_path)
    validate(raw)

    out = raw.rename("load_mw").reset_index().rename(columns={"index": "snapshot"})

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    annual_twh = raw.sum() / 1e6
    peak_mw = raw.max()
    print(
        f"[build_turkey_demand] wrote {len(out)} hourly snapshots to {output_path}\n"
        f"[build_turkey_demand] annual total = {annual_twh:.1f} TWh, "
        f"peak load = {peak_mw:,.0f} MW"
    )
    return out


if __name__ == "__main__":
    try:
        # Populated automatically when run as a Snakemake `script:` step
        input_path = snakemake.input.raw  # noqa: F821
        output_path = snakemake.output[0]  # noqa: F821
    except NameError:
        # Standalone run for manual testing:
        #   python scripts/build_turkey_demand.py [input.csv] [output.csv]
        input_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/epias_load.csv"
        output_path = sys.argv[2] if len(sys.argv) > 2 else "resources/demand_profiles.csv"

    build_demand(input_path, output_path)
