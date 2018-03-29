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

db = plyvel.DB('./past-yearly-data', create_if_missing=False)
prefix = bytes(endpoints.BASE_URL + endpoint[:endpoint.find('{')], 'utf8')

def worker(kv):
  key,value=kv
  print(key)
  value = json.loads(value)
  for item in value['items']:
    appendToDataset(editedPages, item['project'])
    vec = editedPages[item['project']]
    for key, value in item.items():
      key = dashToCamelCase(key)
      if key in editedPages.coords:
        vec = vec.loc[dict([[key, value]])]
    if len(vec.coords.dims) != 1:
      raise ValueError('data does not fully specify non-time axes')
    # Note how we don't deal with granularities other than daily FIXME
    for result in item['results']:
      result = dict(result) # copy to avoid overwriting the data, in case we need it later
      t = result.pop('timestamp')
      vals = list(result.values())
      if len(vals) != 1:
        raise ValueError('More than one data element found in result')
      vec.loc[t] = vals[0]

from multiprocessing import Pool
if __name__ == '__main__':
  with Pool(3) as p:
    l = p.map(worker, db.iterator(prefix=prefix), 10)
    print(len(l))
  
akey = b'https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/anonymous/content/all-activity-levels/daily/20150101/20160101'
value = json.loads(db.get(akey))

# del db

editedPages.to_netcdf('edited-pages.nc')
