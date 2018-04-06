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


ac, lags = acorrc2(edits.values[:, spectralStart:-1])
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

lidx = 1
en = edits.values[lidx, spectralStart:-1]
lag = 550
lag = 2712
lag = 184
plt.figure()
h, xe, ye, i = plt.hist2d(en[:-lag], en[lag:], 50)
plt.xlabel('{} now'.format(endpoint))
plt.ylabel('{} after {} days'.format(endpoint, lag))
plt.title('{}'.format(langs[lidx]))
plt.plot([0, 45e3], [0, 45e3], 'k:')
plt.figure()
plt.scatter(en[:-lag], en[lag:])


def cepstrum(y, fs=1):
    y = detrend(y, type='linear')
    nfft = 16 * 1024
    f = fft.fftfreq(nfft, d=1 / fs)
    f = fft.fftfreq(nfft, d=f[1] - f[0])
    return (fft.fftshift(np.abs(fft.ifft(np.log(np.abs(fft.fft(y, nfft)))))), fft.fftshift(f))


c, f = cepstrum(en, 365.)
plt.figure()
plt.semilogy(f, c)
