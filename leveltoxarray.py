import plyvel
import xarray as xr
import numpy as np
import pandas as pd
import json
import re
import os
import hashlib
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
    if 'type' in value:
        if value['type'].find('errors/unknown_error') >= 0:
            raise ValueError('unknown error in ' + key.decode('utf8') + ', delete and redownload?')
        elif value['type'].find('errors/not_found') >= 0:
            print('not_found in ' + key.decode('utf8') + ', skipping')
            return 0

    hashed = hashlib.md5(key).hexdigest()
    if hashed in ds.attrs:
        return 0

    print(key)
    for item in value['items']:
        thisProject = item['project']
        appendToDataset(ds, thisProject)
        if 'granularity' in item and item['granularity'] != 'daily':
            raise ValueError("Don't yet know how to deal with non-daily data")

        if 'timestamp' in item:
            # `devices` and `views` will be here
            # Lucky the dataset's time axis is called "time" and not "timestamp"!
            vec = dataArrayAndKeysToCut(ds[thisProject], item)
            t = item['timestamp']
            # `views` e.g. is indexed by hours so it might have YYDDMMHH
            if len(t) == len('2018010200'):
                t += '00'
            if 'views' in item:
                vec.loc[t] = item['views']
            elif 'devices' in item:
                vec.loc[t] = item['devices']

        elif "top" in item['results'][0]:
            pageIdList = list(it.islice(filter(lambda s: s.find('-page_id') >= 0, ds.data_vars), 1))
            thisPageId = thisProject + '-page_id'
            appendToDataset(ds, thisPageId, like=pageIdList[0])
            vecPageId = dataArrayAndKeysToCut(ds[thisPageId], item, False)
            vec = dataArrayAndKeysToCut(ds[thisProject], item, False)
            for result in item['results']:
                t = result['timestamp']

                tvec = vec.loc[t]
                tmp = [x['edits'] for x in result['top']]
                tvec.values[:len(tmp)] = tmp

                # x['page_id'] can be `null`??
                tmp = [int(x['page_id'] or 0) for x in result['top']]
                tvecPageId = vecPageId.loc[t]
                tvecPageId.values[:len(tmp)] = tmp

        else:
            vec = dataArrayAndKeysToCut(ds[thisProject], item)
            df = vec.to_pandas()
            for result in item['results']:
                t = result['timestamp']
                keys = list(filter(lambda s: s != 'timestamp', result.keys()))
                if len(keys) != 1:
                    raise ValueError('More than one data element found in result')
                df.at[t] = result[keys[0]]
    ds.attrs[hashed] = '1'
    return 1


def whichEndpoint(url):
    endpoint = list(
        filter(lambda ns: ns[1] == url[:len(ns[1])].decode('utf8'),
               map(lambda ns: [ns[0], endpoints.BASE_URL + ns[1][:ns[1].find('{')]],
                   enumerate(endpoints.URLS))))
    if len(endpoint) != 1:
        raise ValueError('could not determine endpoint for ', url)
    return endpoints.URLS[endpoint[0][0]]


def saveAndMove(ds, filename):
    ds.to_netcdf(filename + '2')
    os.rename(filename + '2', filename)


def groupToDataset(group):
    endpoint, iterator = group
    print(endpoint)
    fi = lambda s: len(s) and s != 'metrics' and s != 'aggregate' and s[0] != '{'
    filename = '_'.join(filter(fi, endpoint.split('/'))) + '.nc'
    try:
        editedPages = xr.open_dataset(filename)
    except FileNotFoundError:
        editedPages = endpointToDataset(endpoint, 'init')
    processed = 0
    for res in iterator:
        processed += updateDataset(editedPages, res)
        if processed > 300:
            processed = 0
            saveAndMove(editedPages, filename)
    if processed > 0: saveAndMove(editedPages, filename)
    return endpoint


if __name__ == '__main__':
    db = plyvel.DB('./past-yearly-data', create_if_missing=False)
    dbscan = db.iterator()
    dbgrouped = it.groupby(dbscan, lambda kv: whichEndpoint(kv[0]))
    for x in dbgrouped:
        groupToDataset(x)
