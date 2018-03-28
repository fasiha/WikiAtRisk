import xarray as xr
import numpy as np
import pandas as pd
import plyvel
import json
import re

dashToCamelCase = lambda s: re.sub(r'-(.)', lambda o: o[1].upper(), s)

import endpoints
endpoint = endpoints.URLS[0]


def endpointToDataArray(endpoint,
                        lang,
                        t=pd.date_range('2001-01-01', '2018-01-01'),
                        dtype=np.int64):
  keys = list(
      filter(lambda key: key in endpoints.defaultCombinations,
             map(lambda s: dashToCamelCase(re.sub(r'[{}]', '', s)),
                 filter(lambda s: len(s) and s[0] == '{',
                        endpoint.split('/')))))
  combinations = list(map(lambda key: endpoints.defaultCombinations[key], keys))
  return xr.DataArray(
      np.zeros([1, t.size] + list(map(len, combinations)), dtype=dtype),
      coords=[[lang], t] + combinations,
      dims=['lang', 'time'] + keys)


en = endpointToDataArray(endpoint, 'en')
fr = endpointToDataArray(endpoint, 'fr')
print(en)
both = xr.concat([en, fr], 'lang')
both.to_netcdf('both.edited-pages.nc')

# db = plyvel.DB('./past-yearly-data', create_if_missing=False)
# akey = b'https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/anonymous/non-content/daily/20160101/20170101'
# aval = json.loads(db.get(akey))
# del db

# s = pd.Series(np.random.randn(len(t)), index=t)
# s.loc['2004-03-01 0:00:00.00Z']
