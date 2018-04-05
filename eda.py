import xarray as xr
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

plt.style.use('ggplot')
plt.ion()

lang = 'en'

for lang in 'en,fr,zh,ja,de,es'.split(','):
    project = lang + '.wikipedia'
    ds = xr.open_dataset('latest/editors__{}.wikipedia.nc'.format(lang))
    plt.figure()
    plt.semilogy(ds.coords['time'], ds[project].loc[dict(
        pageType='content', activityLevel='all-activity-levels')].values)
    plt.legend(ds.coords['editorType'].values)
    plt.xlabel('calendar year')
    plt.ylabel('editors')
    plt.title('Daily editors active on {}.wikipedia'.format(lang))
    plt.savefig('editors.{}.png'.format(lang))
    plt.close()