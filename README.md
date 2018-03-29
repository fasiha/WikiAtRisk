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
Currently there are two pieces:
1. In TypeScript/JavaScript, a package that makes several thousand requests to the Wikimedia analytics server and caches the results as plaintext in a Leveldb, and
2. in Python, a package that transforms the text-based data in Leveldb to numeric data for Numpy and Pandas and friends.

In these instructions, I'll assume you want to do both. So after installing [Git](https://git-scm.com/) and [Node.js](https://nodejs.org/), run the following in your command prompt (each line beginning with a dollar sign, but don't type the dollar sign):
```
$ git clone https://github.com/fasiha/WikiAtRisk.git
$ cd WikiAtRisk
$ npm install
$ npm run build
```
The above will clone this code repository into a new directory (`git …`), enter that directory (`cd …`), intall the JavaScript dependencies (`npm install`, npm being something installed by Node.js), and build the TypeScript source to JavaScript (`npm run …`).

Right now, the only thing this repo does is download a ton of Wikipedia data into a Leveldb database. To get that started, run:
```
$ node downloader.js
```
This fetches a detailed list of [Wikipedia's languages](https://github.com/fasiha/wikipedia-languages/) and then starts downloading several years worth of very interesting data from several Wikipedia projects. It saves the results in the Level database, so feel free to stop and restart the script till you get all the data. The script rate-limits itself so it might take several hours (`MINIMUM_THROTTLE_DELAY_MS` used to be 30 milliseconds, but when I started getting `top-by-edits` data (see below), I increased this to 500 ms). Currently this script hits 130'050 URLs, and the Leveldb weighs roughly 930 megabytes (with Leveldb's automatic compression). If you know TypeScript, you can read [downloader.ts](downloader.ts) to see what all it's doing.

After that finishes, you need to install [Python 3](https://www.python.org/downloads/) (though I recommend [pyenv](https://github.com/pyenv/pyenv)—Clojure and Rust and plenty of other communities have shown us that we shouldn't rely on system-wide installs), then install `virtualenv` by running the following in the command-line (you only have to do this once):
```
$ pip install virtualenv
```
(Pip is the Python installer kind of like how npm is to Node.js.) Next,
```
$ virtualenv .
$ source bin/activate
$ pip install -r requirements.txt --upgrade
```
This creates a virtualenv in the current directory (`virtualenv …`), activates it (`source …`), and installs the libraries that my Python code depends on (`pip …`). After the activation step, your terminal's command prompt should show you some indication that it's in a virtualenv: in my case, it prints a `(WikiAtRisk)` before my prompt. Note that if you open a new terminal window or restart your computer, etc., you need to re-activate the virtualenv to be able to use the packages that it installed: simply rerun `source bin/activate`.

Now you're ready to run the LevelDB-to-xarray ingester:
```
$ python leveltoxarray.py
```
This will spit out several `.nc` NetCDF files that xarray understands. (xarray is a tensor/multidimensional version of Pandas.) **Currently work-in-progress.**

## Data of interest

Source: [Wikipedia REST API](https://wikimedia.org/api/rest_v1/#/).

We download the following:
- `edited-pages/aggregate`: the number of edited pages, daily, between editor types (registered users, bots, and anonymous users)
- `edits`: the total number of edits, daily
- `edited-pages/new`: the number of new pages and who created them, per day
- `editors`: the number of editors active per day, between editor types
- `registered-users`: the daily number of new signups
- `bytes-difference/net`: the daily number of net bytes edited (`added - deleted`), by editor type
- `bytes-difference/absolute`: the daily number of total bytes edited (`added + deleted`)
- `unique-devices`: daily number of unique devices seen, separated by access site (desktop versus mobile site)
- `pageviews`: *daily* (soon hourly!) number of pageviews between access types (desktop browser, mobile browser, and mobile app) and agents (users or crawlers)
- `edited-pages/top-by-edits`: the top hundred most-edited pages for each day, broken down by editor types

all, for the top fifty Wikipedias (by active users), from 2001 to end of 2017. This serves as historical data that's dumped into Leveldb, indexed by the HTTP URL endpoint used to retreive it.

## Languages

(Well, I did have exactly this question: [Why are there so many articles in the Cebuano Wikipedia?](https://www.quora.com/Why-are-there-so-many-articles-in-the-Cebuano-language-on-Wikipedia).)

This package uses my [`wikipedia-languages`](https://github.com/fasiha/wikipedia-languages) library to automatically fetch some metadata from [Wikistats](https://wikistats.wmflabs.org) and stores it locally in `wikilangs.json`. We then select the top fifty Wikipedias by active users.

## Next

Up next on the menu: I need to split the data into training and testing sets—I'm thinking two years for training, then set aside one year for testing, for countries with a four-year election cycle, so that the testing periods cycle through all phases of that? I think I want the test set to have increments of a whole year to ensure I can capture seasonality.

The real juice is a statistical methodology to estimate the future probabilistic distributions of the things we want to predict WaR for.

Finally, we'll need some ways of collecting near-real-time data to get daily WaRs. We can use
- [Quarry](https://quarry.wmflabs.org/query/25783) to run SQL queries on current Wikimedia databases (to get lower latency or finer-grained results than the REST API above), or potentially
- [EventStreams](https://stream.wikimedia.org/?doc) which is a high-volume real-time data feed from Wikimedia of many events that will eventually make it into the REST API.

With these in place, we can publish real-time WaRs!