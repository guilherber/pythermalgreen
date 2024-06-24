from setuptools import setup, find_packages

setup(
    name='pythermalgreen',
    version='0.2.4',
    author='Guilherme Landim-Santos',
    author_email='guisaan.gui@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'pythermalgreen': ['config.yaml'],
    },
    install_requires=[
        'numpy>=1.22.0',
        'rasterio==1.3.10',
        'geopandas==0.14.4',
        'pandas<=2.2.2',
        'shapely==2.0.4'
    ],
    entry_points={
        "cosole_scripts":{
            "pythermalgreen = pythermalgreen:pythermalgreen"
        }
    }
)
