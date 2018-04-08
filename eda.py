import xarray as xr
import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import numpy.fft as fft
from scipy.signal import welch, hamming
import matplotlib.dates as mdates

plt.style.use('ggplot')
plt.ion()
with open('wikilangs.json', 'r') as f:
    wikilangs = sorted(json.load(f), key=lambda o: int(o['activeusers']), reverse=True)
langToData = {o['prefix']: o for o in wikilangs}

langs = 'en,fr,ja,ru,zh,ar,he'.split(',')
endpoint = 'pageviews'
endpoint = 'unique-devices'
endpoint = 'editors'
endpoint = 'bytes-difference_net'
endpoint = 'edits'
ds = xr.merge(
    [xr.open_dataset('latest/{}__{}.wikipedia.nc'.format(endpoint, lang)) for lang in langs])

subdict = dict(pageType='content', editorType=['anonymous', 'user'], agent='user')
for key in list(subdict.keys()):
    if key not in ds.coords:
        del subdict[key]
if 'editorType' in ds.coords:
    edits = ds.loc[subdict].sum('editorType')
    if 'activityLevel' in ds.coords:
        edits.sum('activityLevel')
if 'access' in ds.coords:
    edits = ds.loc[subdict].sum('access')
if 'accessSite' in ds.coords:
    edits = ds.loc[subdict].sum('accessSite')

edits = xr.concat(edits.data_vars.values(), 'lang')
edits.coords['lang'] = langs

plt.figure()
plt.semilogy(edits.coords['time'][:-1], edits.values.T[:-1, :])
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('date')
plt.ylabel(endpoint)
plt.title('Daily Wikipedia {}'.format(endpoint))

# plt.savefig('editors.png')
# plt.savefig('editors.svg')


def dow(lang, edits):
    dayOfWeek = edits['time'].to_pandas().dt.weekday_name
    plt.figure()
    [plt.plot(edits.coords['time'][start::7], edits.loc[lang][start::7]) for start in range(7)]
    plt.legend(dayOfWeek[:7].values)
    plt.xlabel('date')
    plt.ylabel(endpoint)
    plt.title('Daily active {} Wikipedia {}'.format(langToData[lang]['lang'], endpoint))
    # [plt.savefig('{}-dayofweek.{}'.format(lang, f)) for f in 'svg,png'.split(',')]


dow('en', edits)
dow('ja', edits)


def plotSpectralEstimate(f, phi, note='', recip=False, nperseg=None, axes=None):
    if axes is None:
        fig, axes = plt.subplots(len(langs), 1, sharex=True, sharey=True)
    period = 365. / f
    for i, (lang, line) in enumerate(zip(langs, phi)):
        axes[i].loglog(period if recip else f, line / line.max(), color='C{}'.format(i))
        axes[i].set_ylabel(lang)
    for ax in axes:
        plt.setp(ax.get_yticklabels(), visible=False)
        plt.setp(ax.get_yticklines(), visible=False)
        plt.setp(ax.get_xticklines(), visible=False)
    for ax in axes[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)
    axes[-1].set_xlabel('period (days)' if recip else "cycles per year")
    axes[0].set_title('Cyclicity in daily editors' + note)
    if nperseg:
        if recip:
            lo = 10**np.ceil(np.log10(nperseg))
            lo = nperseg * 1.2
            hi = np.min(axes[0].get_xlim())
        else:
            lo = 10**np.floor(np.log10(365 / nperseg)) * .8
            hi = np.max(axes[0].get_xlim())
        axes[0].set_xlim(np.sort((lo, hi)))
    return axes
    # plt.savefig('period.png')
    # plt.savefig('period.svg')


nperseg = 6 * 365
spectralStart = 2100
spectralStartStr = str(edits['time'][spectralStart].values)[:10]
welched = welch(
    edits.values[:, spectralStart:-1],
    fs=365.,
    window='boxcar',
    nperseg=nperseg,
    noverlap=int(nperseg * .1),
    nfft=1024 * 32,
    detrend='linear')
plt.figure()
plt.loglog(365 / welched[0], welched[1].T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('period (days)')
plt.ylabel('spectral density')
plt.title('Welch spectrum: {}, {} year chunks, starting {}'.format(endpoint, nperseg // 365,
                                                                   spectralStartStr))
plt.ylim((1e-4, max(plt.ylim())))


def acorrc(y, maxlags=None):
    maxlags = maxlags or (len(y) - 1)
    a = [1] + [np.corrcoef([y[n:], y[:-n]])[0, 1] for n in range(1, maxlags)]
    return a, range(len(a))


def acorrcArr(arr, maxlags=None):
    a = np.vstack([acorrc(y, maxlags=maxlags)[0] for y in arr])
    return a, range(a.shape[1])


ac, lags = acorrcArr(edits.values[:, spectralStart:-1])
plt.figure()
plt.plot(lags, ac.T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('lag (days)')
plt.ylabel('correlation')
plt.title('Auto-correlation between days, {}, starting {}'.format(endpoint, spectralStartStr))

acf = np.abs(fft.rfft(hamming(ac.shape[1]) * ac, n=1024 * 16, axis=-1))
fac = fft.rfftfreq(16 * 1024, d=1 / 365)
plt.figure()
plt.loglog(365 / fac, acf.T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.title("Auto-correlation's spectrum, {}, starting {}".format(endpoint, spectralStartStr))
plt.xlabel('period (days)')


def sliding(x, nperseg, noverlap=0, f=lambda x: x):
    hop = nperseg - noverlap
    return [
        f(x[i:min(len(x), i + nperseg)]) for i in range(0, hop + len(x) - nperseg, hop)
        if i < len(x)  # needed for noverlap<0
    ]


lagswanted = [7, 365]
ns = [30]
for lagwanted in lagswanted:
    fig, ax = plt.subplots(len(langs), 1, sharex=True, sharey=True)
    for i, lang in enumerate(langs):
        en = edits.values[i, :-1]
        a = en[:-lagwanted]
        b = en[lagwanted:]
        for nperseg in ns:
            c = sliding(
                range(len(a)), nperseg, nperseg - 1, lambda r: np.corrcoef(a[r], b[r])[0, 1])
            tenc = sliding(
                range(len(a)), nperseg, nperseg - 1, lambda r: edits['time'].values[r[0]])
            ax[i].plot(tenc, c)
            ax[i].set_ylabel(lang)
    for a in ax:
        plt.setp(a.get_yticklabels(), visible=False)
        plt.setp(a.get_yticklines(), visible=False)
        plt.setp(a.get_xticklines(), visible=False)
    for a in ax[:-1]:
        plt.setp(a.get_xticklabels(), visible=False)
    ax[0].set_title('Sliding correlation for {} day lag, {} days training, {}'.format(
        lagwanted, ','.join(map(str, ns)), endpoint))

# fig.autofmt_xdate()


def combineSampleMeanVar(m1, v1, n1, m2, v2, n2):
    """See https://stats.stackexchange.com/a/43183"""
    m = (m1 * n1 + m2 * n2) / (n1 + n2)
    v = (n1 * (v1 + m1 * m1) + n2 * (v2 + m2 * m2)) / (n1 + n2) - m * m
    return (m, v, n1 + n2)


def combinecov(x1, y1, Cov1, n1, x2, y2, Cov2, n2):
    """See botom of [1], starting with

    > Likewise, there is a formula for combining the covariances of two sets...
    
    [1] https://en.wikipedia.org/w/index.php?title=Algorithms_for_calculating_variance&oldid=829952267#Online"""
    x3, vx3, _ = combineSampleMeanVar(x1, Cov1[0, 0], n1, x2, Cov2[0, 0], n2)
    y3, vy3, _ = combineSampleMeanVar(y1, Cov1[1, 1], n1, y2, Cov2[1, 1], n2)
    Ca = Cov1[0, 1] * n1
    Cb = Cov2[0, 1] * n2
    Cc = Ca + Cb + (x1 - x2) * (y1 - y2) * n1 * n2 / (n1 + n2)
    c = Cc / (n1 + n2)
    Cov3 = np.array([[vx3, c], [c, vy3]])
    return (x3, y3, Cov3, n1 + n2)


def testCombinecov():
    first = combinecov(1, 20, np.zeros((2, 2)), 1, 2, 21.1, np.zeros((2, 2)), 1)
    firstCov = np.cov([[1, 2.], [20, 21.1]], bias=True)
    assert np.allclose(first[2], firstCov)

    secondCov = np.cov([[1, 2, -1.1], [20, 21.1, 19.5]], bias=True)
    second = combinecov(*first, -1.1, 19.5, np.zeros((2, 2)), 1)
    assert np.allclose(second[2], secondCov)

    thirdCov = np.cov([[1, 2, 1, 2, -1.1], [20, 21.1, 20, 21.1, 19.5]], bias=True)
    third = combinecov(*first, *second)
    assert np.allclose(third[2], thirdCov)

    full = np.random.randn(2, 5)
    fullCov = np.cov(full, bias=True)
    combined = combinecov(
        np.mean(full[0, :2]), np.mean(full[1, :2]), np.cov(full[:, :2], bias=True), 2,
        np.mean(full[0, 2:]), np.mean(full[1, 2:]), np.cov(full[:, 2:], bias=True), 3)
    assert np.allclose(combined[2], fullCov)
    return True


def corrscan(y, lag):
    a = y[lag:]
    b = y[:-lag]
    corr = []
    units = [(a, b, np.zeros((2, 2)), 1) for a, b in zip(a, b)]
    while len(units) > 1:
        suf = [] if len(units) % 2 == 0 else [units[-1]]
        units = [combinecov(*l, *r) for l, r in zip(units[::2], units[1::2])] + suf
        corr.append(
            [(Cov[1, 0] / (np.prod(np.sqrt(np.diag(Cov))) or 1), n) for _, _, Cov, n in units])
    return (corr)


def extents(f):
    delta = f[1] - f[0]
    return [f[0] - delta / 2, f[-1] + delta / 2]


def myim(x, y, *args, **kwargs):
    fig, ax = plt.subplots()
    im = ax.imshow(
        *args,
        **kwargs,
        aspect='auto',
        interpolation='none',
        extent=extents(x) + extents(y),
        origin='lower')
    return fig, ax, im


def slidingCorrScan(y, lag, nperseg=None, noverlap=None, nperseg2=2, noverlap2=1, finallen=1):
    a = y[lag:]
    b = y[:-lag]
    nperseg = nperseg or len(a) // 8
    noverlap = noverlap or nperseg // 2
    corr = []
    idxs = list(map(lambda n: range(n, n + 1), range(len(a))))
    while len(idxs) > finallen:
        idxs = sliding(idxs, nperseg, noverlap,
                       lambda ranges: range(ranges[0][0], 1 + ranges[-1][-1]))
        corr.append([(np.corrcoef([a[idx], b[idx]])[0, 1], len(idx), idx[0]) for idx in idxs])
        nperseg = nperseg2
        noverlap = noverlap2
    return (corr)


def lenStartToArr(lst):
    width = lst[-1][0][1]
    arr = np.zeros((len(lst), width))
    for i, row in enumerate(lst):
        data = np.array(row)
        corrs = data[:, 0]
        starts = data[:, 2].astype(int)
        tmp = np.zeros(width)
        tmp[starts[0]] = corrs[0]
        tmp[starts[1:]] = np.diff(corrs)
        tmp[starts[-1] + 1:] = np.nan
        arr[i, :] = np.cumsum(tmp)
    return arr


en = edits.values[0, :-1]

lagswanted = [7, 365]
cslides = [slidingCorrScan(en, lagwanted, 100, 80) for lagwanted in lagswanted]

for cslide, lagwanted in zip(cslides, lagswanted):
    ten = edits['time'][:-lagwanted - 1]
    ts = mdates.date2num(ten)
    fig, ax, im = myim(ts, [x[0][1] for x in cslide], lenStartToArr(cslide))
    ax.xaxis_date()
    ax.set_xlabel("window's start date")
    ax.set_ylabel('window length (days)')
    im.set_clim((0, 1))
    fig.colorbar(im)
    ax.set_title('Sliding correlations, {} days later, {}'.format(lagwanted, endpoint))

# I like this view I think. For each (X, Y) pixel, X days and Y window length (also days), it says
# "The Y-long window of time starting at X is (not) correlated with the Y-long window starting at
# X-365 days".
