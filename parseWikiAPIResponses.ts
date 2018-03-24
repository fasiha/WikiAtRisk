const level = require('level');
const leveldb = level('./past-yearly-data');
const sqlite3 = require('sqlite3');
const sqldb = new sqlite3.Database(':memory:');
import {URLS, defaultCombinations} from './endpoints';
const flatten1 = (arr: any[]) => arr.reduce((acc, x) => acc.concat(x), []);

const tablesNeeded = URLS.map(
    u => u.split('/').filter(s => !(s === '' || s === 'metrics' || s === 'aggregate' || s.startsWith('{'))).join('/'));
const columnsNeeded = URLS.map(u => u.split('/').filter(s => s.startsWith('{') && s !== '{start}' && s !== '{end}'));
/* Columns are among:
- {project}
- {granularity}
plus we have enumerated defaults for:
- {editor-type}
- {page-type}
- {activity-level}
- {access-site}
- {access}
- {agent}
and the actual data:
- data of interest: either a scalar number OR in case of `top-by-edits`, further data: Array<{page_id: string, edits:
number}>
- timestamp
 */

function parseItems(items: any[]) {
  items.map((item: any) => {
    let metadataKeys = Object.keys(item).filter(x => x !== 'results');
    if (!item.results || item.results.length) { throw new Error('"results" not found or empty'); }
    /*
    Will have to parse: Set {
      'timestamp',
      'abs_bytes_diff',
      'net_bytes_diff',
      'edited_pages',
      'new_pages',
      'top',
      'editors',
      'edits',
      'new_registered_users' }
    */
  })
}

if (require.main === module) {
  (async function() {
    let raw = await leveldb.get(
        "https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/anonymous/content/all-activity-levels/daily/20170101/20180101");
    let hit = JSON.parse(raw);
    // console.log(hit.items[0].results);
    if (hit.items) {
      console.log(hit.items[0].results[0])
      console.log((
          hit.items ||
          []).map((item: any) => new Set(flatten1((item.results || []).map((result: any) => Object.keys(result))))));
    }
  })();
}