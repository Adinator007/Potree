import geopandas as gpd
import sys
import os

def convert_geojson_to_shapefile(geojson_path):
    # Load the GeoJSON file
    geojson_data = gpd.read_file(geojson_path)
    
    # Define the output path
    shapefile_path = geojson_path.replace('.geojson', '.shp')
    
    # Convert and save as shapefile
    geojson_data.to_file(shapefile_path, driver='ESRI Shapefile')
    
    print(f'GeoJSON file converted to shapefile: {shapefile_path}')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python shapeconverter.py <geojson_path>')
        sys.exit(1)

    geojson_path = sys.argv[1]

    if not os.path.exists(geojson_path):
        print(f'GeoJSON file not found: {geojson_path}')
        sys.exit(1)

    convert_geojson_to_shapefile(geojson_path)