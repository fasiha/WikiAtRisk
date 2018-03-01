# Wiki at Risk (WaR)

A play on VaR (value at risk). See Aaron Brown, *Financial risk management for dummies*, chapter six, or Aaron Brown, *Red-blooded risk: the secret history of Wall Street*.

## Data of interest

([source](https://wikimedia.org/api/rest_v1/#/))

- The number of daily edited pages edited
  - `get /metrics/edited-pages/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}` where
    - `project` includes *all* Wikipedias (English, German, Japanese, etc.)
    - `editor-type` includes `anonymous` or `user` (I don't care about bots)
    - `page-type` includes `content` and `non-content`
    - (`activity-level` = `all-activity-levels`)
    - (`granularity` = `daily)
- (Maybe the number of daily *new* pages?)
- The number of daily active editors
  - `get /metrics/editors/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}` where
    - similar to above
- Probably the pageviews
  - `get /metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}`
    - `access` includes `desktop`, `mobile-app`, `mobile-web`
    - `agent` = `user` (don't care about `spiders`)
    - `granularity` = `hourly`

## Languages

Scrape the list from http://wikistats.wmflabs.org/display.php?t=wp which is listed as the source to [this list](https://meta.wikimedia.org/wiki/List_of_Wikipedias).

(Well, I did have exactly this question: [Why are there so many articles in the Cebuano Wikipedia?](https://www.quora.com/Why-are-there-so-many-articles-in-the-Cebuano-language-on-Wikipedia).)


