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

f, phi = periodogram(
    edits[:, 2100:].values, fs=365., window='boxcar', detrend='linear', nfft=1024 * 32)

f, phi = welch(
    edits.values,
    fs=365.,
    window='boxcar',
    nperseg=1000,
    noverlap=500,
    nfft=1024 * 32,
    detrend='linear')

fig, axes = plt.subplots(len(langs), 1, sharex=True, sharey=True)
for i, (lang, line) in enumerate(zip(langs, phi)):
    axes[i].semilogx(365. / f, line / line.max(), color='C{}'.format(i))
    axes[i].set_ylabel(lang)
for ax in axes:
    plt.setp(ax.get_yticklabels(), visible=False)
    plt.setp(ax.get_yticklines(), visible=False)
    plt.setp(ax.get_xticklines(), visible=False)
for ax in axes[:-1]:
    plt.setp(ax.get_xticklabels(), visible=False)
axes[-1].set_xlabel('period (days)')
axes[0].set_title('Cyclicity in daily editors')
# plt.savefig('period.png')
# plt.savefig('period.svg')

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
