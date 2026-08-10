import unicodedata
"""
build_zonal_topology.py — 7-Zone Aggregation for PyPSA-Turkey

Reads 81-province shapefile (TR_adm1.shp), maps each province to one of 7 
macro grid zones, dissolves geometries, computes zonal centroids, 
and outputs the aggregated 7-zone shapefile and zonal metadata.
"""

import logging
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd

INPUT_SHAPE_PATH = "resources/data/province_shapes/TR_adm1.shp"
OUTPUT_SHAPE_PATH = "resources/data/province_shapes/TR_7_zones.shp"
OUTPUT_METADATA_PATH = "resources/data/province_shapes/TR_7_zones_metadata.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logger = logging.getLogger(__name__)

# Verified 81-Province to 7-Zone Mapping Dictionary
TURKEY_7_ZONES = {
    'TR_MAR': ['İstanbul', 'Istanbul', 'Kocaeli', 'Sakarya', 'Bursa', 'Balıkesir', 'Çanakkale', 'Tekirdağ', 'Edirne', 'Kırklareli', 'Yalova', 'Bilecik'],
    'TR_AEG': ['İzmir', 'Aydın', 'Muğla', 'Denizli', 'Manisa', 'Uşak', 'Kütahya', 'Afyonkarahisar'],
    'TR_CAN': ['Ankara', 'Konya', 'Karaman', 'Eskişehir', 'Kayseri', 'Sivas', 'Kırıkkale', 'Aksaray', 'Niğde', 'Nevşehir', 'Kırşehir', 'Yozgat', 'Çankırı'],
    'TR_MED': ['Antalya', 'Mersin', 'Adana', 'Hatay', 'Kahramanmaraş', 'Osmaniye', 'Isparta', 'Burdur'],
    'TR_BLK': ['Trabzon', 'Rize', 'Artvin', 'Ordu', 'Giresun', 'Samsun', 'Sinop', 'Tokat', 'Amasya', 'Çorum', 'Kastamonu', 'Zonguldak', 'Karabük', 'Bartın', 'Düzce', 'Bolu', 'Bayburt', 'Gümüşhane', 'Gumushane'],
    'TR_EAN': ['Erzurum', 'Erzincan', 'Kars', 'Ağrı', 'Iğdır', 'Ardahan', 'Van', 'Muş', 'Bitlis', 'Hakkari', 'Hakkâri', 'Malatya', 'Elazığ', 'Tunceli', 'Bingöl'],
    'TR_SAN': ['Gaziantep', 'Şanlıurfa', 'Diyarbakır', 'Mardin', 'Batman', 'Siirt', 'Şırnak', 'Adıyaman', 'Kilis']
}

# Reverse lookup dictionary: Province Name -> Zone ID
PROVINCE_TO_ZONE = {prov: zone for zone, provs in TURKEY_7_ZONES.items() for prov in provs}


def build_zonal_topology():
    logger.info(f"Loading province shapes from {INPUT_SHAPE_PATH}...")
    gdf_prov = gpd.read_file(INPUT_SHAPE_PATH)

    # Standardize name lookup (handles English vs Turkish naming from Natural Earth)
    # Perform a flexible match against the dictionary
    def find_zone(prov_name):
        if not isinstance(prov_name, str):
            return None
        # Clean whitespace and normalize special characters
        clean_name = unicodedata.normalize('NFC', prov_name.strip())
        
        # Direct lookup
        if clean_name in PROVINCE_TO_ZONE:
            return PROVINCE_TO_ZONE[clean_name]
            
        # Flexible match across normalized keys
        for p_key, zone in PROVINCE_TO_ZONE.items():
            norm_key = unicodedata.normalize('NFC', p_key.strip())
            if norm_key.lower() in clean_name.lower() or clean_name.lower() in norm_key.lower():
                return zone
                
        logger.warning(f"Could not map province '{prov_name}' directly. Check name encoding.")
        return None

    gdf_prov['zone_id'] = gdf_prov['province'].apply(find_zone)

    # Verify all 81 provinces mapped cleanly
    unmapped = gdf_prov[gdf_prov['zone_id'].isna()]
    if not unmapped.empty:
        logger.error(f"Unmapped provinces found ({len(unmapped)}): {unmapped['province'].tolist()}")
        raise ValueError("Failed to map all provinces to the 7 macro zones.")

    logger.info("Aggregating 81 province geometries into 7 Macro Zones...")
    gdf_zones = gdf_prov.dissolve(by='zone_id').reset_index()

    # Calculate centroids (WGS84 EPSG:4326 coordinates)
    # Calculate centroids accurately using UTM Zone 36N (EPSG:32636)
    centroids = gdf_zones.to_crs(epsg=32636).geometry.centroid.to_crs(epsg=4326)
    gdf_zones['x'] = centroids.x
    gdf_zones['y'] = centroids.y

    # Save 7-zone shapefile
    out_path = Path(OUTPUT_SHAPE_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf_zones.to_file(out_path)
    logger.info(f"Saved 7-zone shapefile to {out_path.resolve()}")

    # Output zonal metadata JSON for PyPSA bus creation
    metadata = {}
    for _, row in gdf_zones.iterrows():
        metadata[row['zone_id']] = {
            'x': float(row['x']),
            'y': float(row['y'])
        }

    with open(OUTPUT_METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=4)
    logger.info(f"Saved zonal node metadata to {OUTPUT_METADATA_PATH}")


if __name__ == "__main__":
    build_zonal_topology()
