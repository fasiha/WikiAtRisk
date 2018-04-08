import plyvel
import xarray as xr
import numpy as np
import pandas as pd
import json
import re
import os
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
            # FIXME this might fail because leveldb contains values for keys that ds lacks
            # because endpoints.py doesn't specify them: this will then fail.
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

    # quick setup and checks
    item = value['items'][0]
    thisProject = item['project']
    appendToDataset(ds, thisProject)
    if 'granularity' in item and item['granularity'] != 'daily':
        raise ValueError("Don't yet know how to deal with non-daily data")

    if 'timestamp' in value['items'][0]:
        vec = dataArrayAndKeysToCut(ds[thisProject], item)
        # `views` e.g. is indexed by hours so it might have YYDDMMHH
        fix = lambda t: (t + '00') if len(t) == len('2018010200') else t
        arr = vec.loc[fix(value['items'][0]['timestamp']):fix(value['items'][-1][
            'timestamp'])].values
        key = 'views' if 'views' in item else 'devices'
        if len(value['items']) != arr.size:
            # See https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/mobile-app/spider/daily/20150101/20160101
            # A whole year, only three days with a *mobile* spider. Just iterate in those cases.
            for item in value['items']:
                vec.loc[fix(item['timestamp'])] = item[key]
        else:
            vals = list(map(lambda item: item[key], value['items']))
            arr[:] = vals
    else:
        for item in value['items']:
            if "top" in item['results'][0]:
                pageIdList = list(
                    it.islice(filter(lambda s: s.find('-page_id') >= 0, ds.data_vars), 1))
                thisPageId = thisProject + '-page_id'
                appendToDataset(ds, thisPageId, like=pageIdList[0])

                vecPageId = dataArrayAndKeysToCut(ds[thisPageId], item, False)
                pageIdArr = vecPageId.loc[item['results'][0]['timestamp']:item['results'][-1][
                    'timestamp']].values

                vec = dataArrayAndKeysToCut(ds[thisProject], item, False)
                vecArr = vec.loc[item['results'][0]['timestamp']:item['results'][-1][
                    'timestamp']].values

                for ridx, result in enumerate(item['results']):
                    tmp = [x['edits'] for x in result['top']]
                    vecArr[ridx, :len(tmp)] = tmp

                    # x['page_id'] can be `null`??
                    tmp = [int(x['page_id'] or 0) for x in result['top']]
                    pageIdArr[ridx, :len(tmp)] = tmp

            else:
                k = list(filter(lambda s: s != 'timestamp', item['results'][0].keys()))[0]
                vals = list(map(lambda x: x[k], item['results']))
                vec = dataArrayAndKeysToCut(ds[thisProject], item)
                subvec = vec.loc[item['results'][0]['timestamp']:item['results'][-1]['timestamp']]
                if subvec.size != len(vals):
                    raise ValueError('sub-vector data dimensions mismatch')
                subvec[:] = vals
    return 1


def whichEndpoint(url):
    endpoint = list(
        filter(lambda ns: ns[1] == url[:len(ns[1])].decode('utf8'),
               map(lambda ns: [ns[0], endpoints.BASE_URL + ns[1][:ns[1].find('{')]],
                   enumerate(endpoints.URLS))))
    if len(endpoint) != 1:
        raise ValueError('could not determine endpoint for ', url)
    return endpoints.URLS[endpoint[0][0]]


def whichLanguage(url, endpoint):
    lang = url[len(endpoints.BASE_URL) + endpoint.find('{project}'):]
    return lang[:lang.find(b'/')].decode('utf8')


def whichEndpointLanguage(url):
    endpoint = whichEndpoint(url)
    return {"endpoint": endpoint, "language": whichLanguage(url, endpoint)}


def saveAndMove(ds, filename):
    ds.to_netcdf(filename + '2')
    os.rename(filename + '2', filename)


def groupToDataset(group):
    endlang, iterator = group
    endpoint = endlang['endpoint']
    language = endlang['language']
    fi = lambda s: len(s) and s != 'metrics' and s != 'aggregate' and s[0] != '{'
    filename = 'latest/{e}__{l}.nc'.format(e='_'.join(filter(fi, endpoint.split('/'))), l=language)
    try:
        editedPages = xr.open_dataset(filename)
        return
    except FileNotFoundError:
        editedPages = endpointToDataset(endpoint, language)
    print(endlang)
    for res in iterator:
        updateDataset(editedPages, res)
    saveAndMove(editedPages, filename)
    return endpoint


if __name__ == '__main__':
    db = plyvel.DB('./past-yearly-data', create_if_missing=False)
    dbscan = db.iterator()
    dbgrouped = it.groupby(dbscan, lambda kv: whichEndpointLanguage(kv[0]))
    for x in dbgrouped:
        groupToDataset(x)
