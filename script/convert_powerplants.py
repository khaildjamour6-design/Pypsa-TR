"""convert_powerplants.py — Stage 5a
Converts PyPSA-Earth asset-level powerplants dataset (powerplants.csv) to PyPSA-Turkey
format, maps region names to match buses.csv, and injects real existing solar and wind capacities.

Output: resources/powerplants.csv
"""
import sys
import json
from pathlib import Path
import pandas as pd
from shapely.geometry import Point, shape

# Standard marginal costs (EUR/MWh) for existing fleet
MARGINAL_COSTS = {
    "gas": 60.0,
    "coal": 45.0,        # Hard coal (imported)
    "lignite": 30.0,     # Domestic lignite
    "oil": 120.0,
    "geothermal": 5.0,
    "hydro": 0.0,
    "ror": 0.0,
    "nuclear": 10.0,
    "solar": 0.0,
    "wind": 0.0,
    "biomass": 20.0,
}

# Map GeoJSON / English region names to the exact Turkish names used in buses.csv
REGION_MAP = {
    "Marmara": "Marmara",
    "Aegean": "Ege",
    "Ege": "Ege",
    "Mediterranean": "Akdeniz",
    "Akdeniz": "Akdeniz",
    "Central_Anatolia": "İç Anadolu",
    "Central Anatolia": "İç Anadolu",
    "İç Anadolu": "İç Anadolu",
    "Ic Anadolu": "İç Anadolu",
    "Black_Sea": "Karadeniz",
    "Black Sea": "Karadeniz",
    "Karadeniz": "Karadeniz",
    "Eastern_Anatolia": "Doğu Anadolu",
    "Eastern Anatolia": "Doğu Anadolu",
    "Doğu Anadolu": "Doğu Anadolu",
    "Dogu Anadolu": "Doğu Anadolu",
    "Southeastern_Anatolia": "Güneydoğu Anadolu",
    "Southeastern Anatolia": "Güneydoğu Anadolu",
    "Güneydoğu Anadolu": "Güneydoğu Anadolu",
    "Guneydogu Anadolu": "Güneydoğu Anadolu",
}

# Regional shares for existing Solar (~25.1 GW) and Wind (~8.57 GW)
SOLAR_REGIONAL_SHARES = {
    "İç Anadolu": 0.30,
    "Güneydoğu Anadolu": 0.20,
    "Ege": 0.18,
    "Akdeniz": 0.15,
    "Marmara": 0.10,
    "Doğu Anadolu": 0.05,
    "Karadeniz": 0.02,
}

WIND_REGIONAL_SHARES = {
    "Ege": 0.35,
    "Marmara": 0.30,
    "İç Anadolu": 0.15,
    "Akdeniz": 0.10,
    "Karadeniz": 0.05,
    "Doğu Anadolu": 0.03,
    "Güneydoğu Anadolu": 0.02,
}

TOTAL_EXISTING_SOLAR_MW = 25127.31
TOTAL_EXISTING_WIND_MW = 8568.12

def map_carrier(row):
    fuel = str(row.get("Fueltype", "")).lower()
    tech = str(row.get("Technology", "")).lower()

    if "hydro" in fuel:
        if "run-of-river" in tech or "ror" in tech:
            return "ror"
        return "hydro"
    elif "lignite" in fuel:
        return "lignite"
    elif "hard coal" in fuel or "coal" in fuel:
        return "coal"
    elif "ccgt" in fuel or "ocgt" in fuel or "gas" in fuel:
        return "gas"
    elif "geothermal" in fuel:
        return "geothermal"
    elif "oil" in fuel:
        return "oil"
    elif "nuclear" in fuel:
        return "nuclear"
    else:
        raise ValueError(f"Unhandled fuel/tech combination: Fuel={fuel}, Tech={tech}")

def get_region_for_point(lon, lat, geojson_path):
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    pt = Point(lon, lat)
    for feature in data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(pt):
            raw_reg = feature["properties"]["region"]
            return REGION_MAP.get(raw_reg, raw_reg)
    return None

def convert_powerplants(
    earth_ppl_path: str,
    regions_path: str,
    output_path: str
):
    df = pd.read_csv(earth_ppl_path)
    
    if "Country" in df.columns:
        df = df[df["Country"].isin(["TR", "Turkey", "TUR"])]

    df = df.dropna(subset=["lat", "lon", "Capacity"]).copy()
    df["carrier"] = df.apply(map_carrier, axis=1)

    # Perform spatial point-in-polygon matching
    df["region"] = df.apply(lambda r: get_region_for_point(r["lon"], r["lat"], regions_path), axis=1)
    
    # Map any remaining unmapped or raw region strings
    df["region"] = df["region"].map(lambda x: REGION_MAP.get(x, x))
    df["region"] = df["region"].fillna("Marmara")

    # Build conventional fleet DataFrame using 'region'
    fleet = pd.DataFrame({
        "name": df["Name"].astype(str),
        "region": df["region"],
        "carrier": df["carrier"],
        "p_nom_mw": df["Capacity"].round(2),
        "marginal_cost_eur_per_mwh": df["carrier"].map(MARGINAL_COSTS),
    })

    # Clean name column
    fleet["name"] = fleet["name"].str.replace(r"[^\w\s-]", "", regex=True).str.strip()
    fleet = fleet.drop_duplicates(subset=["name"])

    # Inject existing regional solar and wind
    res_rows = []
    for region, share in SOLAR_REGIONAL_SHARES.items():
        cap_mw = round(TOTAL_EXISTING_SOLAR_MW * share, 2)
        res_rows.append({
            "name": f"existing_solar_{region}",
            "region": region,
            "carrier": "solar",
            "p_nom_mw": cap_mw,
            "marginal_cost_eur_per_mwh": MARGINAL_COSTS["solar"],
        })

    for region, share in WIND_REGIONAL_SHARES.items():
        cap_mw = round(TOTAL_EXISTING_WIND_MW * share, 2)
        res_rows.append({
            "name": f"existing_wind_{region}",
            "region": region,
            "carrier": "wind",
            "p_nom_mw": cap_mw,
            "marginal_cost_eur_per_mwh": MARGINAL_COSTS["wind"],
        })

    res_df = pd.DataFrame(res_rows)
    out = pd.concat([fleet, res_df], ignore_index=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(f"[convert_powerplants] Saved {len(out)} power plant entries to {output_path}")

if __name__ == "__main__":
    earth_ppl = sys.argv[1] if len(sys.argv) > 1 else "powerplants.csv"
    regions_shape = sys.argv[2] if len(sys.argv) > 2 else "resources/shaps/turkey_7regions.geojson"
    out_csv = sys.argv[3] if len(sys.argv) > 3 else "resources/powerplants.csv"

    convert_powerplants(earth_ppl, regions_shape, out_csv)
