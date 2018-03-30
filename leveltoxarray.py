import xarray as xr
import numpy as np
import pandas as pd
import plyvel
import json
import re
import itertools as it
import endpoints


def dashToCamelCase(s: str) -> str:
    return re.sub(r'-(.)', lambda o: o[1].upper(), s)


def endpointToDataset(endpoint: str,
                      project: str,
                      t=pd.date_range('2001-01-01', '2018-01-01'),
                      dtype=np.int64) -> xr.Dataset:
    keys = list(
        filter(lambda key: key in endpoints.defaultCombinations,
               map(lambda s: dashToCamelCase(re.sub(r'[{}]', '', s)),
                   filter(lambda s: len(s) and s[0] == '{', endpoint.split('/')))))
    combinations = list(map(lambda key: endpoints.defaultCombinations[key], keys))
    alldims = ['time'] + keys
    allcoords = [t] + combinations
    ds = xr.Dataset()
    ds[project] = (alldims, np.zeros([t.size] + list(map(len, combinations)), dtype=dtype))
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


def updateDataset(ds, keyval):
    key, value = keyval
    value = json.loads(value)
    project = value['items'][0]['project']
    if 'done-' + project in ds.attrs:
        return ''
    print(key)
    for item in value['items']:
        appendToDataset(ds, item['project'])
        vec = ds[item['project']]
        for key, value in item.items():
            key = dashToCamelCase(key)
            if key in ds.coords:
                vec = vec.loc[dict([[key, value]])]
        if len(vec.coords.dims) != 1:
            raise ValueError('data does not fully specify non-time axes')
        # Note how we don't deal with granularities other than daily FIXME
        for result in item['results']:
            # copy to avoid overwriting the data, in case we need it later
            result = dict(result)
            t = result.pop('timestamp')
            vals = list(result.values())
            if len(vals) != 1:
                raise ValueError('More than one data element found in result')
            vec.loc[t] = vals[0]
    return project


if __name__ == '__main__':
    import os

    endpoint = endpoints.URLS[0]
    filename = 'edited-pages.nc'

    try:
        editedPages = xr.open_dataset(filename)
    except FileNotFoundError:
        editedPages = endpointToDataset(endpoint, 'init')

    prefix = bytes(endpoints.BASE_URL + endpoint[:endpoint.find('{')], 'utf8')

    db = plyvel.DB('./past-yearly-data', create_if_missing=False)

    dbscan = db.iterator(prefix=prefix)
    dbgrouped = it.groupby(
        dbscan,
        lambda kv: kv[0][:len(endpoints.BASE_URL) + len('XY.wikipedia') + endpoint.find('{')])

    for (group, groupit) in dbgrouped:
        print('\nGROUP ', group)
        for res in groupit:
            project = updateDataset(editedPages, res)
        if len(project):
            editedPages.attrs['done-' + project] = 1
            editedPages.to_netcdf(filename + '2')
            os.rename(filename + '2', filename)
