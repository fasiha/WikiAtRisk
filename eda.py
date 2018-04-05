import xarray as xr
import json
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

edits = ds.loc[dict(pageType='content', activityLevel='all-activity-levels')].sum('editorType')
edits = xr.concat(edits.data_vars.values(), 'lang')
edits.coords['lang'] = langs

plt.figure()
plt.semilogy(edits.coords['time'][:-1], edits.values.T[:-1, :])
plt.legend([langToData[lang]['lang'] for lang in langs])
plt.xlabel('calendar year')
plt.ylabel('editors')
plt.title('Daily active Wikipedia editors')
plt.savefig('editors.png')
plt.savefig('editors.svg')

from scipy.signal import periodogram

f, phi = periodogram(
    edits[:, 2100:].values, fs=365., window='boxcar', detrend='linear', nfft=1024 * 32)

fig, axes = plt.subplots(len(langs), 1, sharex=True, sharey=True)
for i, (lang, line) in enumerate(zip(langs, phi)):
    axes[i].plot(f, line / line.max(), color='C{}'.format(i))
    axes[i].set_ylabel(lang)
for ax in axes:
    plt.setp(ax.get_yticklabels(), visible=False)
    plt.setp(ax.get_yticklines(), visible=False)
    plt.setp(ax.get_xticklines(), visible=False)
for ax in axes[:-1]:
    plt.setp(ax.get_xticklabels(), visible=False)
axes[-1].set_xlabel('cycles per year')
axes[0].set_title('Cyclicity in daily editors')
plt.savefig('period.png')
plt.savefig('period.svg')