from functools import reduce
import json
import pandas as pd
import xarray as xr
import numpy as np
import numpy.fft as fft
import numpy.ma as ma
from scipy.signal import welch, hamming
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors

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
endpoint = 'editors'
endpoint = 'edits'
endpoint = 'edited-pages_new'
endpoint = 'editors'
endpoint = 'edited-pages'
endpoint = 'registered-users_new'
ds = xr.merge(
    [xr.open_dataset('latest/{}__{}.wikipedia.nc'.format(endpoint, lang)) for lang in langs])

subdict = dict(pageType='content', editorType=['anonymous', 'user'], agent='user')
for key in list(subdict.keys()):
    if key not in ds.coords:
        del subdict[key]
if 'editorType' in ds.coords:
    edits = ds.loc[subdict].sum('editorType')
    if 'activityLevel' in ds.coords:
        edits = edits.sum('activityLevel')
elif 'access' in ds.coords:
    edits = ds.loc[subdict].sum('access')
elif 'accessSite' in ds.coords:
    edits = ds.loc[subdict].sum('accessSite')
else:
    edits = ds.loc[subdict]

edits = xr.concat(edits.data_vars.values(), 'lang')
edits.coords['lang'] = langs


def save(fname, num=None):
    plt.figure(num or plt.gcf().number)
    plt.savefig(fname + '.svg')
    plt.savefig(fname + '.png', dpi=150)


plt.figure()
plt.semilogy(edits.coords['time'][:-1], edits.values.T[:-1, :])
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('date')
plt.ylabel(endpoint)
plt.title('Daily Wikipedia {}'.format(endpoint))
save('1-several-langs-{}'.format(endpoint))


def dow(lang, edits):
    dayOfWeek = edits['time'].to_pandas().dt.weekday_name
    plt.figure()
    [plt.plot(edits.coords['time'][start:-1:7], edits.loc[lang][start:-1:7]) for start in range(7)]
    plt.legend(dayOfWeek[:7].values)
    plt.xlabel('date')
    plt.ylabel(endpoint)
    plt.title('Daily active {} Wikipedia {}'.format(langToData[lang]['lang'], endpoint))

    resh2 = lambda x, n: x.ravel()[:(x.size // n) * n].reshape((-1, n))
    remmax = lambda x: x / np.max(x)
    dowMedian = np.median(resh2(edits.loc[lang, '2012-12-31':].values, 7), axis=0)
    print('| Day |  Median {} | % of max |'.format(endpoint))
    print('|-----|-----------------|----------|')
    days = edits['time'].loc['2012-12-31':].to_pandas().dt.weekday_name[:7].tolist()
    print('\n'.join([
        '| {} | {:,} | {:.2%} |'.format(day, int(med), pct)
        for med, pct, day in zip(dowMedian, remmax(dowMedian), days)
    ]))


dow('en', edits)
save('2-day-of-week-en-{}'.format(endpoint))
dow('ja', edits)
save('2-day-of-week-ja-{}'.format(endpoint))


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
save('3-welch-several-langs-{}'.format(endpoint))


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
save('4-acf-several-langs-{}'.format(endpoint))

acf = np.abs(fft.rfft(hamming(ac.shape[1]) * ac, n=1024 * 16, axis=-1))
fac = fft.rfftfreq(16 * 1024, d=1 / 365)
plt.figure()
plt.loglog(365 / fac, acf.T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.title("Auto-correlation's spectrum, {}, starting {}".format(endpoint, spectralStartStr))
plt.xlabel('period (days)')
save('5-acfspectrum-several-langs-{}'.format(endpoint))


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
    save('6-sliding-corr-{}-several-langs-{}'.format(lagwanted, endpoint))

# fig.autofmt_xdate()


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
    return corr


def lenStartToArrTail(lst, lag):
    width = lst[-1][0][1] + 365
    arr = np.zeros((len(lst), width))
    for i, row in enumerate(lst):
        data = np.array(row)
        corrs = data[:, 0]
        lens = data[:, 1].astype(int)
        starts = data[:, 2].astype(int)
        ends = starts + lag + lens
        tmp = np.repeat(np.nan, width)
        for e, f, c in zip(ends[0:-1], ends[1:], corrs[1:]):
            tmp[e:f] = c
        dstart = starts[1] - starts[0] if starts.size > 1 else 20
        end = np.minimum(width, ends[0])
        tmp[(end - dstart):end] = corrs[0]
        arr[i, :] = tmp
    return arr


en = edits.values[0, :-1]

lagswanted = [7, 365]
cslides = [slidingCorrScan(en, lagwanted, 100, 80) for lagwanted in lagswanted]


class SqueezedNorm(matplotlib.colors.Normalize):
    """Via https://stackoverflow.com/a/44438440/500207"""

    def __init__(self, vmin=None, vmax=None, mid=0, s1=2, s2=2, clip=False):
        self.vmin = vmin  # minimum value
        self.mid = mid  # middle value
        self.vmax = vmax  # maximum value
        self.s1 = s1
        self.s2 = s2
        f = lambda x, zero, vmax, s: np.abs((x - zero) / (vmax - zero))**(1. / s) * 0.5
        self.g = lambda x, zero,vmin,vmax, s1,s2: f(x,zero,vmax,s1)*(x>=zero) - \
                                             f(x,zero,vmin,s2)*(x<zero)+0.5
        matplotlib.colors.Normalize.__init__(self, vmin, vmax, clip)

    def __call__(self, value, clip=None):
        r = self.g(value, self.mid, self.vmin, self.vmax, self.s1, self.s2)
        return np.ma.masked_array(r)


mynorm = SqueezedNorm(vmin=-.4, vmax=1, mid=0., s1=1., s2=1.)
# See https://stackoverflow.com/a/31052741/500207
colors1 = plt.cm.Oranges(np.linspace(0., 1, 128))  #[::-1, :]
colors2 = plt.cm.viridis(np.linspace(0, 1, 128))
colors = np.vstack((colors1, colors2))
mymap = mcolors.LinearSegmentedColormap.from_list('my_colormap', colors)
for cslide, lagwanted in zip(cslides, lagswanted):
    ten = edits['time'][:-1]
    ts = mdates.date2num(ten)
    fig, ax, im = myim(
        ts, [x[0][1] for x in cslide],
        ma.masked_invalid(lenStartToArrTail(cslide, lagwanted)),
        cmap=mymap,
        norm=mynorm)
    ax.xaxis_date()
    ax.set_xlabel("window end date")
    ax.set_ylabel('window length (days)')
    im.set_clim((-0.4, 1))
    fig.colorbar(im)
    ax.set_title('Sliding correlations, {} days prior lag, en, {}'.format(lagwanted, endpoint))
    save('7-sliding-heatmap-{}-{}-{}'.format(lagwanted, 'en', endpoint))

# I like this view I think. For each (X, Y) pixel, X days and Y window length (also days), it says
# "The Y-long window of time starting at X is (not) correlated with the Y-long window starting at
# X-365 days".

# so what's going on here?
df = pd.DataFrame(
    lenStartToArrTail(cslides[1], lagswanted[1]).T,
    index=edits['time'].values[:-1],
    columns=[x[0][1] for x in cslides[1]])
enddate = '2007-06-01'
nwindow = df.loc[enddate].idxmin()

exactendidx = df.index.get_loc(enddate)
arr = np.array(cslides[1][df.columns.get_loc(nwindow)])
corrs, lens, starts = arr.T
ends = starts + lagswanted[1] + lens
endidx = (ends < exactendidx).sum()
end = int(ends[endidx])
actual = np.corrcoef(en[end - nwindow:end], en[end - nwindow - 365:end - 365])[0, 1]
expected = df.loc[enddate].loc[nwindow]
print({'actual': actual, 'expected': expected})

# Example 2
enddate = '2009-01-01'
nwindow = 365 * 3

end = df.index.get_loc(enddate)
foo, bar = en[end - nwindow:end], en[end - nwindow - 365:end - 365]
foo = foo.reshape((3, -1))
bar = bar.reshape((3, -1))
plt.figure()
[plt.scatter(x, y) for x, y in zip(foo, bar)]
plt.xlabel('{}'.format(endpoint))
plt.ylabel('{}, 365 days ago'.format(endpoint))
plt.title('The 2007 discontinuity')
plt.legend(['2005/2006', '2006/2007', '2007/2008'])
save('8-peak-wiki-en-{}'.format(endpoint))
# Recall that Peak Wiki happened late April 2007, but edits had been stagnant since Jan 2007.
#
# The long dark diagonal slash of low correlation in the sliding correlation heatmap reflects this:
# the first half of 2006 sees rapidly-increasing edits, and 365 days later (first half of 2007) is
# stagnant edits, which destoys collinearity.
#
# The second half of 2006 continued seeing rapid growth, and this correlates nicely with the second
# half of 2007: recall that the collapse started early May 2007, but saw a dead-cat bounce in July,
# before bottoming out in early August. August 2006 through Jan 2007 look similar enough to a year
# later that they correlate well (~0.5).
#
# The presence of the high-growth portion of early 2006 in the 365-day lag correlations reduces
# correlation values by destroying collinearity, due to its marked contrast to the first half of 2007
# (which saw flat edits till April and then freefall May, )

# Example 3

# Another phase change is indicated by the dark black vertical section of low correlation in late
# 2015. Specifically, both halves of 2014 are uncorrelated with the both halves of 2015.
# In a nutshell: 2014 continues the previous several years' drop. Most years see either flat or
# dropping edits for the first half, then a substantial drop in mid-year that sometimes recovers
# before the December crash. 2015 however began with a strong recovery after the holiday break,
# followed by a robust plateau throughout the year, frequently breaking highs, and spiking edits
# to levels last seen in early 2011.
#
# Correlation is low because we have a region of steady decline correlating poorly against a region
# of stagnation-then-growth. Note how the dark region moves up and a bit right: any window that
# includes that last half of 2015 (and therefore correlates it against the last half of 2014) is
# plagued by low correlation. However, if the segment includes much more before or after that last
# half of 2015, the correlation returns, as this data conjoined with prior/subsequent data emulate
# collinearity.

# Example 4
enddate = '2016-01-01'
yrs = 2
nwindow = 365 * yrs

end = df.index.get_loc(enddate)

foo, bar = en[end - nwindow:end], en[end - nwindow - 365:end - 365]
resh = lambda x, n: x.ravel()[:(x.size // n) * n].reshape((n, -1))
foo = resh(foo, yrs * 2)
bar = resh(bar, yrs * 2)
plt.figure()
[plt.scatter(x, y) for x, y in zip(foo, bar)]
plt.xlabel('{}'.format(endpoint))
plt.ylabel('{}, 365 days ago'.format(endpoint))
plt.title('The 2015 discontinuity')
plt.legend(list(map(lambda n: str(n), list(np.arange(yrs * 2) / 2 + 2014))))
save('9-2014-bump-en-{}'.format(endpoint))
