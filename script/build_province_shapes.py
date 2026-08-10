"""
build_province_shapes.py — GIS Boundary Extraction for PyPSA-Turkey

Downloads Natural Earth Admin-1 boundaries for Turkey (TR), cleans 
province names, and saves the shapefile for zonal mapping.
"""

import logging
from pathlib import Path
import cartopy.io.shapereader as shpreader
import geopandas as gpd

NATURAL_EARTH_RESOLUTION = "10m"
NATURAL_EARTH_DATA_SET = "admin_1_states_provinces"
DEFAULT_CRS = 4326  # WGS84
DEFAULT_SHAPE_OUTPATH = "resources/data/province_shapes/TR_adm1.shp"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def fetch_turkey_shapes():
    logger.info("Fetching Natural Earth shapefiles for Turkey (ISO: TR)...")
    shpfilename = shpreader.natural_earth(
        resolution=NATURAL_EARTH_RESOLUTION,
        category="cultural",
        name=NATURAL_EARTH_DATA_SET,
    )
    reader = shpreader.Reader(shpfilename)
    records = list(reader.records())

    tr_records = [rec for rec in records if rec.attributes.get("iso_a2") == "TR" or rec.attributes.get("adm0_a3") == "TUR"]
    logger.info(f"Extracted {len(tr_records)} provincial boundaries.")
    return tr_records


def convert_to_geodataframe(records) -> gpd.GeoDataFrame:
    data = {
        "province": [r.attributes.get("name_en", r.attributes.get("name")) for r in records],
        "iso_code": [r.attributes.get("iso_3166_2") for r in records],
    }
    geometries = [r.geometry for r in records]

    gdf = gpd.GeoDataFrame(data, geometry=geometries, crs=f"EPSG:{DEFAULT_CRS}")
    gdf["province"] = gdf["province"].str.strip()
    gdf.sort_values(by="province", inplace=True)
    gdf.reset_index(drop=True, inplace=True)
    return gdf


if __name__ == "__main__":
    records = fetch_turkey_shapes()
    tr_gdf = convert_to_geodataframe(records)

    out_path = Path(DEFAULT_SHAPE_OUTPATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tr_gdf.to_file(out_path)
    logger.info(f"Saved Turkey province shapefile to {out_path.resolve()}")
