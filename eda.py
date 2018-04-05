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
ds = xr.merge([xr.open_dataset('latest/editors__{}.wikipedia.nc'.format(lang)) for lang in langs])

edits = ds.loc[dict(
    pageType='content', activityLevel='all-activity-levels', editorType=['anonymous',
                                                                         'user'])].sum('editorType')
edits = xr.concat(edits.data_vars.values(), 'lang')
edits.coords['lang'] = langs


def dow(lang, edits):
    dayOfWeek = edits['time'].to_pandas().dt.weekday_name
    plt.figure()
    [plt.plot(edits.coords['time'][start::7], edits.loc[lang][start::7]) for start in range(7)]
    plt.legend(dayOfWeek[:7].values)
    plt.xlabel('date')
    plt.ylabel('editors')
    plt.title('Daily active {} Wikipedia editors'.format(langToData[lang]['lang']))
    [plt.savefig('{}-dayofweek.{}'.format(lang, f)) for f in 'svg,png'.split(',')]


dow('en', edits)
dow('ja', edits)

plt.figure()
plt.semilogy(edits.coords['time'][:-1], edits.values.T[:-1, :])
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('date')
plt.ylabel('editors')
plt.title('Daily active Wikipedia editors')
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


nperseg = 6 * 365
welcher = lambda spectralStart: welch(
    edits.values[:, spectralStart:],
    fs=365.,
    window='hann',
    nperseg=nperseg,
    noverlap=int(nperseg * .9),
    nfft=1024 * 32,
    detrend='linear')
ax = None
for spectralStart in [500, 2100]:
    ax = plotSpectralEstimate(
        *welcher(spectralStart), ' (Welch)', nperseg=nperseg, recip=True, axes=ax)
[plt.savefig('welch.{}'.format(f)) for f in 'svg,png'.split(',')]

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
