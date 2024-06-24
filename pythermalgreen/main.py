
import rasterio as rio
from rasterio.features import rasterize
from geopandas import GeoDataFrame
from shapely.geometry import Point
from rasterio.plot import show
import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from rasterio import features


class pythermalgreen:
    def __init__(self, tst_file, ndvi_file, output):
        self.tst_file = tst_file
        self.ndvi_file = ndvi_file
        self.output = output



    def sample_raster_values(self, gdf, raster_file, column_name):
        values = []
        with rasterio.open(raster_file) as src:
            for geom in gdf.geometry:
                x, y = geom.x, geom.y
                for val in src.sample([(x, y)]):
                    values.append(val[0] if not np.isnan(val[0]) else None)
        gdf[column_name] = values

    def process(self):
        with rio.Env():
            with rio.open(ndvi_file) as src:
                crs = src.crs
                xmin, ymax = np.around(src.xy(0.00, 0.00), 9)
                xmax, ymin = np.around(src.xy(src.height - 1, src.width - 1), 9)
                x = np.linspace(xmin, xmax, src.width)
                y = np.linspace(ymax, ymin, src.height)
                xs, ys = np.meshgrid(x, y)
                zs = src.read(1)
                mask = src.read_masks(1) > 0
                xs, ys, zs = xs[mask], ys[mask], zs[mask]
        data = {"X": pd.Series(xs.ravel()),
                "Y": pd.Series(ys.ravel())} 

        df = pd.DataFrame(data=data)
        geometry = gpd.points_from_xy(df.X, df.Y)
        gdf = gpd.GeoDataFrame(df, crs=crs, geometry=geometry)

        sample_raster_values(gdf, ndvi_file, 'NDVI')
        sample_raster_values(gdf, tst_file, 'TST')

        df = gdf.drop(columns='geometry')
        quartis_temperatura = np.percentile(df['TST'], [25, 50, 75])

        def condicao_alta_temperatura_e_baixo_ndvi(temperatura, ndvi):
            if temperatura >= quartis_temperatura[2] and ndvi < 0.6: 
                return 1
            else:
                return 0

        df['Condicao'] = df.apply(lambda row: condicao_alta_temperatura_e_baixo_ndvi(row['TST'], row['NDVI']), axis=1)
        df = df[df['Condicao'] != 0]

        with rasterio.open(ndvi_file) as src:
            out_shape = src.shape
            transform = src.transform
            crs = src.crs
            raster = src.read(1, masked=True)
        geometry = [Point(xy) for xy in zip(df.X, df.Y)]
        df8 = df.drop(['X', 'Y'], axis=1)
        gdf = GeoDataFrame(df8, crs="EPSG:4326", geometry=geometry)
        geom = gdf['geometry']
        geom_value = [(geom, value) for geom, value in zip(gdf.geometry, gdf['Condicao'])]
        rasterized = rasterize(
            geom_value,
            out_shape=raster.shape,
            transform=transform,
            all_touched=True,
            dtype=rasterio.float32
        )

        filtered_rasterized = np.where(rasterized == 0, np.nan, rasterized)
        with rio.open(output, "w",
                    driver="GTiff",
                    transform=transform,
                    dtype=rasterio.float32,
                    count=1,
                    crs=crs,
                    width=src.width,
                    height=src.height
                    ) as dst:
            dst.write(filtered_rasterized, indexes=1)
        raster = rasterio.open(output)
        show(raster)
