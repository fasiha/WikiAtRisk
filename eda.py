import xarray as xr
import json
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

plt.style.use('ggplot')
plt.ion()
with open('wikilangs.json', 'r') as f:
    wikilangs = sorted(json.load(f), key=lambda o: int(o['activeusers']), reverse=True)
langToData = {o['prefix']: o for o in wikilangs}

langs = 'en,fr,ja,ru,zh,ar,he'.split(',')
endpoint = 'bytes-difference_net'
endpoint = 'editors'
ds = xr.merge(
    [xr.open_dataset('latest/{}__{}.wikipedia.nc'.format(endpoint, lang)) for lang in langs])

subdict = dict(
    pageType='content', activityLevel='all-activity-levels', editorType=['anonymous', 'user'])
for key in list(subdict.keys()):
    if key not in ds.coords:
        del subdict[key]
edits = ds.loc[subdict].sum('editorType')
edits = xr.concat(edits.data_vars.values(), 'lang')
edits.coords['lang'] = langs


def dow(lang, edits):
    dayOfWeek = edits['time'].to_pandas().dt.weekday_name
    plt.figure()
    [plt.plot(edits.coords['time'][start::7], edits.loc[lang][start::7]) for start in range(7)]
    plt.legend(dayOfWeek[:7].values)
    plt.xlabel('date')
    plt.ylabel(endpoint)
    plt.title('Daily active {} Wikipedia {}'.format(langToData[lang]['lang'], endpoint))
    [plt.savefig('{}-dayofweek.{}'.format(lang, f)) for f in 'svg,png'.split(',')]


dow('en', edits)
dow('ja', edits)

plt.figure()
plt.semilogy(edits.coords['time'][:-1], edits.values.T[:-1, :])
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('date')
plt.ylabel(endpoint)
plt.title('Daily active Wikipedia {}'.format(endpoint))
plt.savefig('editors.png')
plt.savefig('editors.svg')

from scipy.signal import periodogram, welch, stft


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


def aliaze(f, fs, nperiods=1):
    offset = np.arange(-abs(nperiods), abs(nperiods) + .5) * fs
    if len(offset) == 0: offset = 0
    lo = np.floor(f / (fs / 2)) * (fs / 2)
    hi = lo + fs / 2
    underLo = lo - (f - lo)
    overHi = hi + (hi - f)
    return (np.hstack([f, overHi]) + offset[:, np.newaxis]).ravel()


def aliasFreq(f, fs):
    lo = np.floor(f / fs) * fs
    hi = lo + fs
    return np.min(np.abs([lo - f, hi - f]))


nperseg = 6 * 365
spectralStart = 2100
welched = welch(
    edits.values[:, spectralStart:],
    fs=365.,
    window='boxcar',
    nperseg=nperseg,
    noverlap=int(nperseg * .1),
    nfft=1024 * 32,
    detrend='constant')
ax = plotSpectralEstimate(*welched, ' (Welch, constant)', nperseg=nperseg, recip=True)
ax[-1].set_ylim((1e-7, max(ax[-1].get_ylim())))
[plt.savefig('welch.{}'.format(f)) for f in 'svg,png'.split(',')]

fracs = [.1, .3, .5, .7, .9]
toperiod = lambda fp: [365 / fp[0], fp[1]]
ws = list(map(toperiod, map(lambda n: welch(
    edits.values[0, 2100:],
    fs=365.,
    window='hann',
    nperseg=nperseg,
    noverlap=int(nperseg * n),
    nfft=1024 * 32,
    detrend='linear'), fracs)))
plt.figure()
plt.loglog(*sum(map(list, ws), []))
plt.legend(list(map(lambda f: '{}% overlap'.format(f), fracs)))
plt.xlabel('period (days)')

fP, phiP = periodogram(
    edits[:, spectralStart:].values, fs=365., window='boxcar', detrend='linear', nfft=1024 * 32)
plotSpectralEstimate(fP, phiP, ' (periodogram)')

db20 = lambda x: 20 * np.log10(np.abs(x))
f, t, Zxx = stft(
    edits.values,
    fs=365.,
    window='boxcar',
    nperseg=365,
    noverlap=360,
    nfft=1024 * 16,
    detrend='linear')
en = db20(np.squeeze(Zxx[0, :, :]))
en -= en.max()
plt.figure()
m = plt.pcolormesh(2001 + t, f, en, vmax=0, vmin=-60)
plt.xlabel('year')
plt.ylabel('cycles/year')

from scipy.signal import correlate


def acorrBiased(y):
    """Obtain the biased autocorrelation and its lags
  """
    r = correlate(y, y) / len(y)
    l = np.arange(-(len(y) - 1), len(y))
    return r, l


def acorrc(y, maxlags=None):
    maxlags = maxlags or (len(y) - 1)
    a = [1] + [np.corrcoef([y[n:], y[:-n]])[0, 1] for n in range(1, maxlags)]
    return a, range(len(a))


def acorrc2(arr, maxlags=None):
    a = np.vstack([acorrc(y, maxlags=maxlags)[0] for y in arr])
    return a, range(a.shape[1])


ac, lags = acorrc2(edits.values[:, 1000:-1])
plt.figure()
plt.plot(lags, ac.T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('lag (days)')
plt.ylabel('correlation')
plt.title('Auto-correlation btw days(-1 to +1), {}'.format(endpoint))

import numpy.fft as fft
from scipy.signal import detrend, hamming

acf = np.abs(fft.rfft(hamming(ac.shape[1]) * ac, n=1024 * 16, axis=-1))
fac = fft.rfftfreq(16 * 1024, d=1 / 365)
plt.figure()
plt.loglog(365 / fac, acf.T)
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.title('Spectrum of ACF')
plt.xlabel('period (days)')


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


def raggedsToArr(corr):
    arr = np.array([corr[0]])
    width = arr.shape[1]
    for row in corr[1:]:
        stack = np.repeat(row, int(np.ceil(width / len(row))))[:width]
        arr = np.vstack([arr, stack])
    return arr


def corrscan(y, lag):
    a = y[lag:]
    b = y[:-lag]
    corr = []
    units = [(a, b, np.zeros((2, 2)), 1) for a, b in zip(a, b)]
    while len(units) > 1:
        suf = [] if len(units) % 2 == 0 else [units[-1]]
        units = [combinecov(*l, *r) for l, r in zip(units[::2], units[1::2])] + suf
        corr.append([Cov[1, 0] / np.prod(np.sqrt(np.diag(Cov))) for _, _, Cov, _ in units])
    return raggedsToArr(corr)
