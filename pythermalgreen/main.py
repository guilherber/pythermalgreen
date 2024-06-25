import rasterio as rio
from rasterio.features import rasterize
from geopandas import GeoDataFrame
from shapely.geometry import Point
from rasterio.plot import show
import pandas as pd
import geopandas as gpd
import numpy as np
import pylandstats as pls
import warnings

class pythermalgreen:
    def __init__(self, tst_file, ndvi_file, output):
        self.tst_file = tst_file
        self.ndvi_file = ndvi_file
        self.output = output

    def sample_raster_values(self, gdf, raster_file, column_name):
        values = []
        with rio.open(raster_file) as src:
            for geom in gdf.geometry:
                x, y = geom.x, geom.y
                for val in src.sample([(x, y)]):
                    values.append(val[0] if not np.isnan(val[0]) else None)
        gdf[column_name] = values

    def process(self):
        with rio.Env():
            with rio.open(self.ndvi_file) as src:
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

        self.sample_raster_values(gdf, self.ndvi_file, 'NDVI')
        self.sample_raster_values(gdf, self.tst_file, 'TST')

        df = gdf.drop(columns='geometry')
        quartis_temperatura = np.percentile(df['TST'], [25, 50, 75])

        def condicao_alta_temperatura_e_baixo_ndvi(temperatura, ndvi):
            if temperatura >= quartis_temperatura[2] and ndvi < 0.5:
                return 1
            else:
                return 0

        df['Condicao'] = df.apply(lambda row: condicao_alta_temperatura_e_baixo_ndvi(row['TST'], row['NDVI']), axis=1)
        df = df[df['Condicao'] != 0]

        with rio.open(self.ndvi_file) as src:
            out_shape = src.shape
            transform = src.transform
            crs = src.crs
            raster = src.read(1, masked=True)

        geometry = [Point(xy) for xy in zip(df.X, df.Y)]
        df8 = df.drop(['X', 'Y'], axis=1)
        gdf = GeoDataFrame(df8, crs=crs, geometry=geometry)
        geom = gdf['geometry']
        geom_value = [(geom, value) for geom, value in zip(gdf.geometry, gdf['Condicao'])]

        rasterized = rasterize(
            geom_value,
            out_shape=raster.shape,
            transform=transform,
            all_touched=True,
            dtype=rio.float32
        )

        filtered_rasterized = np.where(rasterized == 0, np.nan, rasterized)

        with rio.open(self.output, "w",
                      driver="GTiff",
                      transform=transform,
                      dtype=rio.float32,
                      count=1,
                      crs=crs,
                      width=src.width,
                      height=src.height) as dst:
            dst.write(filtered_rasterized, indexes=1)

    def metrics(self):
        try:
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            warnings.filterwarnings("ignore", message="Module .* has not been compiled for Transonic-Numba")
            raster = rio.open(self.output)
            show(raster)
            data = raster.read(1, masked=True)

            unique_values = np.unique(data.compressed())
            if len(unique_values) <= 1:
                print(
                    f"The raster contains only a single class (value {unique_values[0]}). No meaningful metrics can be computed.")
                return
            ls = pls.Landscape(self.output)
            ls.nodata = 0  
            patch_metrics_df = ls.compute_landscape_metrics_df()
            if patch_metrics_df.empty:
                print(
                    "The DataFrame is empty. This is likely due to the raster containing insufficient class diversity.")
            else:
                with pd.option_context('display.max_rows', None, 'display.max_columns', None):
                    print(patch_metrics_df)

        except ValueError as e:
            print(f"ValueError: {e}")
        except RuntimeWarning as e:
            print(f"RuntimeWarning: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        finally:
            warnings.resetwarnings()
