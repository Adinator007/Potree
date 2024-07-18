import os
import numpy as np
import laspy
import pandas as pd
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from sklearn.cluster import DBSCAN
import geopandas as gpd
from shapely.geometry import LineString, mapping
import fiona
from fiona.crs import from_epsg

# Adatok betöltése
stems_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Kalvaria-ter-drone_stems.las"
tree_positions_path = "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/torzs_koordinatak_plusz.txt"

# Törzs pontfelhő betöltése
stems_las = laspy.read(stems_path)
stems_points = np.vstack((stems_las.x, stems_las.y, stems_las.z)).transpose()

# Fa pozíciók betöltése
tree_positions = pd.read_csv(tree_positions_path, sep=",", header=None, names=["label", "x", "y", "z"])

# DBSCAN paraméterek
eps = 0.15
min_samples = 7
measurement_interval = 0.075

def filter_points(points, center, radius):
    dist = np.sqrt((points[:, 0] - center[0])**2 + (points[:, 1] - center[1])**2)
    return points[dist <= radius]

def slice_points(points, center_z, height, thickness):
    return points[(points[:, 2] >= center_z + height - thickness) & (points[:, 2] <= center_z + height + thickness)]

# Main output folder
output_folder = "outputs"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Shapefile létrehozása
for index, tree in tree_positions.iterrows():
    tree_pos = tree[['x', 'y', 'z']].values
    tree_label = str(int(tree['label']))

    hull_lines = []

    for i in range(-4, 3):  # 4 below, 2 above
        height = 1.0 + i * measurement_interval

        # Pontok szűrése 2m sugarú körben
        filtered_points = filter_points(stems_points, tree_pos[:2], 2.0)

        # Pontok kivágása adott magasságban
        sliced_points = slice_points(filtered_points, tree_pos[2], height, 0.05)

        if sliced_points.shape[0] == 0:
            print(f"No points found for tree {tree_label} at height {height:.2f}m.")
            continue

        # DBSCAN algoritmus az outlierek szűrésére
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(sliced_points[:, :2])
        labels = clustering.labels_

        unique_labels = set(labels)
        unique_labels.discard(-1)
        if not unique_labels:
            print(f"No valid clusters found for tree {tree_label} at height {height:.2f}m.")
            continue
        largest_cluster_label = max(unique_labels, key=list(labels).count)

        inlier_points = sliced_points[labels == largest_cluster_label]

        if len(inlier_points) == 0:
            print(f"No inlier points found for tree {tree_label} at height {height:.2f}m.")
            continue

        hull = ConvexHull(inlier_points[:, :2])
        hull_points = inlier_points[hull.vertices]

        # LineString létrehozása a konvex burokhoz (LineStringZ)
        hull_line = LineString([(p[0], p[1], p[2]) for p in hull_points])
        hull_lines.append({
            'geometry': hull_line,
            'label': f"{tree_label}_{i}"
        })

        # Kép mentése az illesztésről
        plt.figure(figsize=(10, 10))
        plt.scatter(sliced_points[:, 0], sliced_points[:, 1], c='lightgrey', label='All Points')
        plt.scatter(inlier_points[:, 0], inlier_points[:, 1], c='darkgreen', label='Inliers')
        plt.scatter(sliced_points[labels == -1, 0], sliced_points[labels == -1, 1], c='red', label='Outliers')

        for simplex in hull.simplices:
            plt.plot(inlier_points[simplex, 0], inlier_points[simplex, 1], 'k-')

        plt.title(f'Tree {tree_label} - Diameter Measurement at {height:.2f}m')
        plt.xlabel('X')
        plt.ylabel('Y')
        plt.legend()

        tree_folder = os.path.join(output_folder, tree_label)
        if not os.path.exists(tree_folder):
            os.makedirs(tree_folder)

        plt.savefig(os.path.join(tree_folder, f'{tree_label}_{i}_stem_diameter.png'))
        plt.close()

    # Shapefile mentése az ID-hoz
    if hull_lines:
        schema = {
            'geometry': '3D LineString',
            'properties': {'label': 'str'}
        }
        shapefile_path = os.path.join(tree_folder, f"{tree_label}_stem_diameters.shp")
        with fiona.open(shapefile_path, 'w', driver='ESRI Shapefile', crs=from_epsg(23700), schema=schema) as c:
            for line in hull_lines:
                c.write({
                    'geometry': mapping(line['geometry']),
                    'properties': {'label': line['label']}
                })
        print(f"Shapefile successfully created for tree {tree_label} at {shapefile_path}.")
    else:
        print(f"No valid lines found for tree {tree_label}.")


