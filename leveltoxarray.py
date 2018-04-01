import plyvel
import xarray as xr
import numpy as np
import pandas as pd
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
    size = [t.size] + list(map(len, combinations))
    top = endpoint.find('/top-by-edits/') >= 0
    if top:
        alldims += ['topidx']
        allcoords += [np.arange(100)]
        size += [100]
        dtype = np.int32
    ds = xr.Dataset()
    ds[project] = (alldims, np.zeros(size, dtype=dtype))
    for dim, coord in zip(alldims, allcoords):
        ds.coords[dim] = coord
    if top:
        dtype = np.int64
        project += '-page_id'
        ds[project] = (alldims, np.zeros(size, dtype=dtype))
        for dim, coord in zip(alldims, allcoords):
            ds.coords[dim] = coord
    return ds


def appendToDataset(ds: xr.Dataset, newProject: str, like=None):
    if len(ds.data_vars) == 0:
        raise ValueError('dataset needs to have at least one data variable')
    if newProject not in ds:
        existing = ds[like or (list(it.islice(ds.data_vars, 1))[0])]
        arr = existing.values
        dims = existing.coords.dims
        ds[newProject] = (dims, np.zeros_like(arr))


def dataArrayAndKeysToCut(da, keyvals, full=True):
    for key, value in keyvals.items():
        key = dashToCamelCase(key)
        if key in da.coords:
            da = da.loc[dict([[key, value]])]
    if full and len(da.coords.dims) != 1:
        raise ValueError('data does not fully specify non-time axes')
    return da


def updateDataset(ds, keyval):
    key, value = keyval
    value = json.loads(value)
    project = value['items'][0]['project']
    if 'done-' + project in ds.attrs:
        return ''
    print(key)
    for item in value['items']:
        thisProject = item['project']
        appendToDataset(ds, thisProject)
        if 'granularity' in item and item['granularity'] != 'daily':
            raise ValueError("Don't yet know how to deal with non-daily data")

        if 'timestamp' in item:
            vec = dataArrayAndKeysToCut(ds[thisProject], item)
            # `devices` and `views` will be here
            if 'views' in item:
                vec.loc[item['timestamp']] = item['views']
            elif 'devices' in item:
                vec.loc[item['timestamp']] = item['devices']

        elif "top" in item['results'][0]:
            pageIdList = list(it.islice(filter(lambda s: s.find('-page_id') >= 0, ds.data_vars), 1))
            thisPageId = thisProject + '-page_id'
            appendToDataset(ds, thisPageId, like=pageIdList[0])
            vecPageId = dataArrayAndKeysToCut(ds[thisPageId], item, False)
            vec = dataArrayAndKeysToCut(ds[thisProject], item, False)
            for result in item['results']:
                t = result['timestamp']
                tvec = vec.loc[t]
                tvecPageId = vecPageId.loc[t]
                for (topidx, top) in enumerate(result['top']):
                    tvec[topidx] = top['edits']
                    tvecPageId[topidx] = int(top['page_id'])

        else:
            vec = dataArrayAndKeysToCut(ds[thisProject], item)
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

    fi = lambda s: len(s) and s != 'metrics' and s != 'aggregate' and s[0] != '{'
    dbnames = list(map(lambda s: '_'.join(filter(fi, s.split('/'))), endpoints.URLS))

    endidx = -1
    endpoint = endpoints.URLS[endidx]
    filename = dbnames[endidx] + '.nc'

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
