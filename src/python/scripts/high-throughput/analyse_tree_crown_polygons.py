import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points
import fiona
from fiona.crs import from_epsg
import json
from datetime import datetime

# Load the coordinates
tree_positions_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/torzs_koordinatak_plusz.txt"
tree_positions = pd.read_csv(tree_positions_path, sep=",", header=None, names=["label", "x", "y", "z"])

# Load the polygon shapefile
polygons_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Potree/examples/kalvaria_pcd/FaKoronaPoligonok.shp"
polygons_gdf = gpd.read_file(polygons_path)

# Main output folder
output_folder = "outputs"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def get_closest_polygon(tree_point, polygons):
    # Find the nearest polygon if no polygon contains the point
    nearest_geom = nearest_points(tree_point, polygons.unary_union)[1]
    closest_polygon = polygons[polygons.geometry == nearest_geom]
    return closest_polygon.iloc[0]

for index, tree in tree_positions.iterrows():
    tree_pos = Point(tree['x'], tree['y'], tree['z'])
    tree_label = str(int(tree['label']))

    # Find all polygons containing the tree position
    containing_polygons = polygons_gdf[polygons_gdf.contains(tree_pos)]

    if not containing_polygons.empty:
        chosen_polygon = containing_polygons.iloc[0]
    else:
        # If no polygon contains the point, find the closest polygon
        chosen_polygon = get_closest_polygon(tree_pos, polygons_gdf)
    
    # Ensure the chosen polygon is 3D (PolygonZ)
    if chosen_polygon.geometry.has_z:
        polygon_coords = list(chosen_polygon.geometry.exterior.coords)
    else:
        polygon_coords = [(x, y, tree['z']) for x, y in chosen_polygon.geometry.exterior.coords]

    polygon_z = Polygon(polygon_coords)

    # Calculate crown diameter
    crown_diameter = polygon_z.length/np.pi

    # Create tree folder
    tree_folder = os.path.join(output_folder, tree_label)
    if not os.path.exists(tree_folder):
        os.makedirs(tree_folder)

    # Save the chosen polygon to a new shapefile in the tree folder using fiona
    schema = {
        'geometry': 'Polygon',
        'properties': {'label': 'str'}
    }
    shapefile_path = os.path.join(tree_folder, f"{tree_label}_polygon.shp")
    with fiona.open(shapefile_path, 'w', driver='ESRI Shapefile', crs=from_epsg(23700), schema=schema) as c:
        c.write({
            'geometry': {
                'type': 'Polygon',
                'coordinates': [polygon_coords]
            },
            'properties': {'label': tree_label}
        })
    print(f"Polygon shapefile successfully created for tree {tree_label} at {shapefile_path}.")

    # JSON file handling
    json_filename = f"{tree_label}_original_measurements.json"
    json_filepath = os.path.join(tree_folder, json_filename)

    if not os.path.exists(json_filepath):
        data = {
            "username": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "date": datetime.now().isoformat(),
            "measurements": {
                "crownDiameter": crown_diameter,
                "stemDiameter": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                "height": 10  # Placeholder value, assuming height is not measured in this script
            }
        }
        with open(json_filepath, 'w') as json_file:
            json.dump(data, json_file, indent=4)
        print(f"JSON file successfully created for tree {tree_label} at {json_filepath}.")
    else:
        with open(json_filepath, 'r+') as json_file:
            data = json.load(json_file)
            data['measurements']['crownDiameter'] = crown_diameter
            json_file.seek(0)
            json.dump(data, json_file, indent=4)
            json_file.truncate()
        print(f"JSON file successfully updated for tree {tree_label} at {json_filepath}.")

print("All polygon shapefiles successfully created.")
