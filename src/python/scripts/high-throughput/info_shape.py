import fiona
import geopandas as gpd

def print_shapefile_info(shapefile_path):
    # Read the shapefile
    with fiona.open(shapefile_path, 'r') as src:
        # Print basic information
        print(f"Shapefile: {shapefile_path}")
        print(f"Driver: {src.driver}")
        print(f"CRS: {src.crs}")
        print(f"Number of features: {len(src)}")
        
        # Print schema
        print("\nSchema:")
        for key, value in src.schema.items():
            print(f"  {key}: {value}")
        
        # Print feature information
        for feature in src:
            print("\nFeature:")
            for key, value in feature.items():
                if key == "geometry":
                    geom_type = value['type']
                    coords = value['coordinates']
                    print(f"  Geometry Type: {geom_type}")
                    print(f"  Coordinates: {coords}")
                else:
                    print(f"  {key}: {value}")

# Paths to shapefiles
shapefile_paths = [
    "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Potree/outputs/75479826/75479826_stem_diameters.shp",
    "/mnt/d/ChimeraSolutions/Dendrocomplex/Dendro_Dayjob_tooling/high-throughput/Potree/outputs/60464481/60464481_stem_diameters.shp"
]

# Print information for each shapefile
for shapefile_path in shapefile_paths:
    print_shapefile_info(shapefile_path)
    print("\n" + "="*80 + "\n")
