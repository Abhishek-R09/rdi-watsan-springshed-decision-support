"""Build-time smoke check of the actual image's native GIS libraries and backend startup."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    import boto3
    import numpy as np
    import pyflwdir
    import pyproj
    import rasterio
    import scipy
    import shapely
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    import render_app
    from spring_tool_server import Tool
    from module_b_springshed import load_factors, rathi_fit

    # Exercise the GTiff driver as well as importing its Python wrapper.
    with MemoryFile() as memory:
        with memory.open(driver='GTiff', width=3, height=3, count=1, dtype='float32',
                         crs='EPSG:4326', transform=from_origin(78.5, 30.0, .001, .001)) as dataset:
            dataset.write(np.ones((3, 3), dtype='float32'), 1)
        with memory.open() as dataset:
            if dataset.read(1).shape != (3, 3) or dataset.crs.to_epsg() != 4326:
                raise RuntimeError('The image cannot read its GeoTIFF/CRS test')
    tool = Tool()
    if not tool.health()['ok'] or not tool.springs():
        raise RuntimeError('The image cannot initialise the backend and spring catalogue')
    if not load_factors() or rathi_fit()['n'] != 35:
        raise RuntimeError('The recharge rules or literature reference table are unavailable')
    if not (ROOT / 'app/dist/index.html').is_file():
        raise RuntimeError('The image has no built frontend')
    print('Runtime check passed: native GIS libraries, GeoTIFF/CRS, backend, reference tables and frontend.')


if __name__ == '__main__':
    main()
