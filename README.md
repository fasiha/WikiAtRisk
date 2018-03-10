# Wiki at Risk (WaR)

A play on **VaR** (**value at risk**). See Aaron Brown, _Financial risk management for dummies_, chapter six, or Aaron Brown, _Red-blooded risk: the secret history of Wall Street_, but in a nutshell, in finance, the VaR of a fixed portfolio is the amount of money it will lose over one day (or some time horizon) with 95% probability (or some fixed probability). The portfolio is expected to experience losses exceeding this 95% daily VaR five percent of the time, that is, a **VaR break** is expected on average once every twenty days. To quote Brown, "VaR is ***not*** a worst-case outcome. VaR is the best-case outcome on the worst 5 percent of days," so VaR breaks could see (much) heavier losses than the VaR. According to Brown, a good methodology for computing VaR should, in a backtest, produce the right number of breaks, independently distributed over time (i.e., not clumping), and independent of the level of the VaR—in fact, be independent of anything. The discipline of finding data sources and statistical methods that allow a risk manager to consistently produce a good daily VaR is said to provide "crucial advance warnings" of crises (admittedly with many false alarms). Brown: "Time after time in the past, little disturbances in VaR have been the only warning that the markets gave of crises to come; and research to make VaR better always seems to pay off later—usually in totally unexpected ways—in making risk decisions."

**WaR** (**Wiki at Risk**) seeks to estimate and publish good daily 95% VaRs for:
- edits,
- edited pages,
- active editors,

or some combination thereof, for at least the top fifty busiest (identified loosely) Wikipedias, with the goals of
1. identifying the data sets that give us good WaRs, in order to
2. give us early warning of geopolitical or network events that impact global Wikipedia activity.

We wish as much to understand the world through Wikipedia as to understand Wikipedia through the world.

## Yeah, yeah, I know, how do I run this?
After installing [Git](https://git-scm.com/) and [Node.js](https://nodejs.org/), run the following in your command prompt (each line beginning with a dollar sign, but don't type the dollar sign):
```
$ git clone https://github.com/fasiha/WikiAtRisk.git
$ cd WikiAtRisk
$ npm install
$ npm run build
```
The above will clone this code repository into a new directory, enter that directory, intall the JavaScript dependencies, and build the TypeScript source to JavaScript.

Right now, the only thing this repo does is download a ton of Wikipedia data into a Leveldb database. To get that started, run:
```
$ node downloader.js
```
This fetches a detailed list of [Wikipedia's languages](https://github.com/fasiha/wikipedia-languages/) and then starts downloading several years worth of very interesting data from several Wikipedia projects. It saves the results in the Level database, so feel free to stop and restart the script till you get all the data. The script rate-limits itself so it might take an hour or two.

Meanwhile, if you know TypeScript, you can read [downloader.ts](downloader.ts) to see what all it's doing.

## Data of interest

([source](https://wikimedia.org/api/rest_v1/#/))

- The number of daily edited pages edited
  - `get /metrics/edited-pages/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}` where
    - `project` includes *all* Wikipedias (English, German, Japanese, etc.)
    - `editor-type` includes `anonymous` or `user` (I don't care about bots)
    - `page-type` includes `content` and `non-content`
    - (`activity-level` = `all-activity-levels`)
    - (`granularity` = `daily`)
- (Maybe the number of daily *edits* (i.e., multiple edits are possible per page))
- (Maybe the number of daily *new* pages?)
- The number of daily active editors
  - `get /metrics/editors/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}` where
    - similar to above
- Probably the pageviews
  - `get /metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}`
    - `access` includes `desktop`, `mobile-app`, `mobile-web`
    - `agent` = `user` (don't care about `spiders`)
    - `granularity` = `hourly`
- I also think I want to record the daily list of top-100 pages that saw most edits.

## Languages

Obtain the [CSV](http://wikistats.wmflabs.org/api.php?action=dump&table=wikipedias&format=csv) (compare to [interactive table](http://wikistats.wmflabs.org/display.php?t=wp)) which is listed as the source to [this list](https://meta.wikimedia.org/wiki/List_of_Wikipedias).

(Well, I did have exactly this question: [Why are there so many articles in the Cebuano Wikipedia?](https://www.quora.com/Why-are-there-so-many-articles-in-the-Cebuano-language-on-Wikipedia).)


