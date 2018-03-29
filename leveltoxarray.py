import xarray as xr
import numpy as np
import pandas as pd
import plyvel
import json
import re

import endpoints
endpoint = endpoints.URLS[0]


def dashToCamelCase(s: str) -> str:
  return re.sub(r'-(.)', lambda o: o[1].upper(), s)


def endpointToDataset(endpoint: str,
                      project: str,
                      t=pd.date_range('2001-01-01', '2018-01-01'),
                      dtype=np.int64) -> xr.Dataset:
  keys = list(
      filter(lambda key: key in endpoints.defaultCombinations,
             map(lambda s: dashToCamelCase(re.sub(r'[{}]', '', s)),
                 filter(lambda s: len(s) and s[0] == '{',
                        endpoint.split('/')))))
  combinations = list(map(lambda key: endpoints.defaultCombinations[key], keys))
  alldims = ['time'] + keys
  allcoords = [t] + combinations
  ds = xr.Dataset()
  ds[project] = (alldims,
                 np.zeros([t.size] + list(map(len, combinations)), dtype=dtype))
  for dim, coord in zip(alldims, allcoords):
    ds.coords[dim] = coord
  return ds


def appendToDataset(ds: xr.Dataset, newProject: str):
  if len(ds.data_vars) == 0:
    raise ValueError('dataset needs to have at least one data variable')
  if newProject not in ds:
    existing = list(ds.data_vars.values())[0]
    arr = existing.values
    dims = existing.coords.dims
    ds[newProject] = (dims, 0 * arr)


editedPages = endpointToDataset(endpoint, 'en.wikipedia')
appendToDataset(editedPages, 'fr.wikipedia')
editedPages.to_netcdf('edited-pages.nc')

# db = plyvel.DB('./past-yearly-data', create_if_missing=False)
# prefix = bytes(endpoints.BASE_URL + endpoint[:endpoint.find('{')], 'utf8')
# for key, value in db.iterator(prefix=prefix):
#   print(key)
#   value = json.loads(value)
#   # for item in items:
#   break

# akey = b'https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/anonymous/non-content/daily/20160101/20170101'
# aval = json.loads(db.get(akey))
# del db

# s = pd.Series(np.random.randn(len(t)), index=t)
# s.loc['2004-03-01 0:00:00.00Z']
