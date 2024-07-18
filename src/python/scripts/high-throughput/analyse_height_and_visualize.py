import os
import numpy as np
import laspy
import matplotlib.pyplot as plt
import pandas as pd
from scipy.spatial import KDTree
import geopandas as gpd
from shapely.geometry import LineString, Point

# Load the point clouds
canopy_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Kalvaria-ter-drone_canopy.las"
stems_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Kalvaria-ter-drone_stems.las"
tree_positions_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/torzs_koordinatak_plusz.txt"

# Load canopy point cloud
canopy_las = laspy.read(canopy_path)
canopy_points = np.vstack((canopy_las.x, canopy_las.y, canopy_las.z)).transpose()

# Load tree positions
tree_positions = pd.read_csv(tree_positions_path, sep=",", header=None, names=["label", "x", "y", "z"])

# Define grid size and radius for tree height calculation
grid_size = 0.5
density_threshold = 100
search_radius = 5.0

# Create grid
min_x, min_y, min_z = np.min(canopy_points, axis=0)
max_x, max_y, max_z = np.max(canopy_points, axis=0)

x_bins = np.arange(min_x, max_x, grid_size)
y_bins = np.arange(min_y, max_y, grid_size)
z_bins = np.arange(min_z, max_z, grid_size)

# Digitize points to create a 3D histogram
x_indices = np.digitize(canopy_points[:, 0], x_bins)
y_indices = np.digitize(canopy_points[:, 1], y_bins)
z_indices = np.digitize(canopy_points[:, 2], z_bins)

# Create a 3D matrix to count points in each grid cell
grid = np.zeros((len(x_bins), len(y_bins), len(z_bins)))

for i in range(canopy_points.shape[0]):
    grid[x_indices[i]-1, y_indices[i]-1, z_indices[i]-1] += 1

# Create the heatmap data
heatmap = np.zeros((len(x_bins), len(y_bins)))

for ix in range(len(x_bins)):
    for iy in range(len(y_bins)):
        # Get the highest dense cube in this (x, y) column
        column = grid[ix, iy, :]
        dense_cubes = np.where(column > density_threshold)[0]
        if len(dense_cubes) > 0:
            highest_dense_cube = dense_cubes[-1]
            heatmap[ix, iy] = z_bins[highest_dense_cube]

# Find the highest grid points within the specified radius for each tree
tree_heights = []

# Create a KDTree for fast spatial search
canopy_kdtree = KDTree(canopy_points[:, :2])

def compute_score(tree_pos, point):
    vertical_distance = abs(tree_pos[2] - point[2])
    horizontal_distance = np.sqrt((tree_pos[0] - point[0])**2 + (tree_pos[1] - point[1])**2)
    return point[2] - np.exp(horizontal_distance)

# Main output folder
output_folder = "outputs"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

for index, tree in tree_positions.iterrows():
    tree_pos = tree[['x', 'y', 'z']].values
    tree_label = str(int(tree['label']))
    
    # Find points within search_radius
    idx = canopy_kdtree.query_ball_point(tree_pos[:2], search_radius)
    points_in_radius = canopy_points[idx]

    if points_in_radius.shape[0] == 0:
        continue
    
    # Find the highest scoring point in the radius
    scores = [compute_score(tree_pos, point) for point in points_in_radius]
    highest_point = points_in_radius[np.argmax(scores)]
    
    tree_height = highest_point[2] - tree_pos[2]
    tree_heights.append([tree_label, tree_pos[0], tree_pos[1], tree_pos[2], highest_point[0], highest_point[1], highest_point[2], tree_height])

    # Create lines for visualization
    tree_point = Point(tree_pos[0], tree_pos[1], tree_pos[2])
    grid_point = Point(highest_point[0], highest_point[1], highest_point[2])
    line = LineString([tree_point, grid_point])
    
    # Create GeoDataFrame and save to shapefile
    gdf = gpd.GeoDataFrame({'geometry': [line]}, crs="EPSG:23700")
    
    tree_folder = os.path.join(output_folder, tree_label)
    if not os.path.exists(tree_folder):
        os.makedirs(tree_folder)
        
    shapefile_path = os.path.join(tree_folder, f"{tree_label}_height.shp")
    gdf.to_file(shapefile_path)
    print(f"Height shapefile successfully created for tree {tree_label} at {shapefile_path}.")

# Output to CSV
tree_heights_df = pd.DataFrame(tree_heights, columns=['label', 'tree_x', 'tree_y', 'tree_z', 'grid_x', 'grid_y', 'grid_z', 'height'])
tree_heights_df.to_csv(os.path.join(output_folder, 'tree_heights.csv'), index=False)

print("All height shapefiles and CSV successfully created.")
