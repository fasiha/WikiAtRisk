const level = require('level');
const leveldb = level('./past-yearly-data');
// const sqlite3 = require('sqlite3');
import sqlite3 from 'sqlite3';
const sqldb = new sqlite3.Database('./granular.sqlite');
import {URLS, defaultCombinations} from './endpoints';
const flatten1 = (arr: any[]) => arr.reduce((acc, x) => acc.concat(x), []);
const camelCase = require('camelcase');

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

function initializeTablesFromItems(globalKey: string, items: any[], sqldb: sqlite3.Database) {
  items.forEach((item: any) => {
    let nonResultValues = [ 'devices', 'views' ];

    if (!item.results && item.timestamp && (nonResultValues.some(s => item.hasOwnProperty(s)))) {
      let target = nonResultValues.find(key => item.hasOwnProperty(key));
      if (!target) { throw new Error('non-result target not found'); }
      let metadataKeys: string[] = Object.keys(item);
      let textKeysSet = new Set(metadataKeys);
      textKeysSet.delete('timestamp');
      nonResultValues.forEach(k => textKeysSet.delete(k));
      let textKeys = Array.from(textKeysSet);
      let textKeysString = textKeys.map(s => `${camelCase(s)} TEXT`).sort().join(', ');
      sqldb.run(`CREATE TABLE IF NOT EXISTS war_${target} (id INTEGER PRIMARY KEY, ${target} INTEGER, timestamp TEXT, ${
          textKeysString})`);
      return;
    }

    if (item.results.length === 0) { throw new Error('"results" not found or empty in ' + globalKey); }
    let metadataKeysOrig: string[] = Object.keys(item).filter(x => x !== 'results');
    let metadataKeys = metadataKeysOrig.map(s => camelCase(s));
    let resultsSet: Set<string> = new Set(flatten1(item.results.map((result: any) => Object.keys(result))));
    resultsSet.delete('timestamp');

    let metaString = metadataKeys.map(key => `${key} TEXT`).sort().join(', ');
    for (let result of resultsSet) {
      if (result === 'top') {
        return; // FIXME
      } else {
        sqldb.run(`CREATE TABLE IF NOT EXISTS war_${result} (id INTEGER PRIMARY KEY, ${
            result} INTEGER, timestamp TEXT, ${metaString})`);
      }
    }
  });
}

function parseItems(globalKey: string, items: any[], sqldb: sqlite3.Database) {
  items.forEach((item: any) => {
    let nonResultValues = [ 'devices', 'views' ];

    if (!item.results && item.timestamp && (nonResultValues.some(s => item.hasOwnProperty(s)))) {
      let target = nonResultValues.find(key => item.hasOwnProperty(key));
      if (!target) { throw new Error('non-result target not found'); }
      let metadataKeys: string[] = Object.keys(item);

      let textKeysSet = new Set(metadataKeys);
      textKeysSet.delete('timestamp');
      nonResultValues.forEach(k => textKeysSet.delete(k));
      let textKeys = Array.from(textKeysSet).sort();
      let textValues = textKeys.map(k => item[k]);

      let textKeysString = textKeys.map(s => `${camelCase(s)} TEXT`).join(', ');
      let qs = metadataKeys.map(_ => '?').join(', ');
      let textKeysOnly = textKeys.map(s => camelCase(s)).join(',');
      let statement = sqldb.prepare(`INSERT INTO war_${target} (${target}, timestamp, ${textKeysOnly}) VALUES (${qs})`);
      statement.run(+item[target], item.timestamp, ...textValues);
      return;
    }

    if (item.results.length === 0) { throw new Error('"results" not found or empty in ' + globalKey); }
    if (item.results[0].hasOwnProperty('top')) { return; }
    let metadataKeysOrig: string[] = Object.keys(item).filter(x => x !== 'results').sort();
    let metadataKeys = metadataKeysOrig.map(s => camelCase(s));
    let resultsSet: Set<string> = new Set(flatten1(item.results.map((result: any) => Object.keys(result))));
    resultsSet.delete('timestamp');

    let metadataValues = metadataKeysOrig.map(k => item[k]);
    let metaString = metadataKeys.map(key => `${key} TEXT`).join(', ');
    let qs = Array.from(Array(metadataKeys.length + 2), _ => '?').join(', ');
    const makeColumnString = (result: string) => `${result}, timestamp, ${metadataKeys.join(',')}`;
    let resultToStatement: any = {};
    resultsSet.forEach(result => resultToStatement[result]
                       = sqldb.prepare(`INSERT INTO war_${result} (${makeColumnString(result)}) VALUES (${qs})`));
    for (let result of item.results) {
      let key = Object.keys(result).find(k => k !== 'timestamp');
      if (!key) { throw new Error('key not found'); }
      resultToStatement[key].run(+result[key], result.timestamp, ...metadataValues);
    }
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
    let allEnglish
        = `https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/anonymous/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/anonymous/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/group-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/group-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/name-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/name-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/user/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/absolute/aggregate/en.wikipedia/user/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/anonymous/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/anonymous/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/group-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/group-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/name-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/name-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/user/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/bytes-difference/net/aggregate/en.wikipedia/user/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/anonymous/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/anonymous/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/group-bot/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/group-bot/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/name-bot/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/name-bot/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/user/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/user/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/anonymous/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/anonymous/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/group-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/group-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/name-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/name-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/user/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/new/en.wikipedia/user/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/anonymous/content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/anonymous/non-content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/group-bot/content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/group-bot/non-content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/name-bot/content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/name-bot/non-content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/user/content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/user/non-content/daily/20170101/20170201
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/anonymous/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/anonymous/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/group-bot/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/group-bot/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/name-bot/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/name-bot/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/user/content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia/user/non-content/all-activity-levels/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/anonymous/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/anonymous/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/group-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/group-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/name-bot/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/name-bot/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/user/content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/edits/aggregate/en.wikipedia/user/non-content/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/desktop/spider/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/desktop/user/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/mobile-app/spider/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/mobile-app/user/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/mobile-web/spider/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/mobile-web/user/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/registered-users/new/en.wikipedia/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/unique-devices/en.wikipedia/desktop-site/daily/20170101/20180101
    https://wikimedia.org/api/rest_v1/metrics/unique-devices/en.wikipedia/mobile-site/daily/20170101/20180101`;
    let testKeys = allEnglish.trim().split('\n').map(s => s.trim());
    sqldb.serialize(async () => {
      for (let key of testKeys) {
        let hit = JSON.parse(await leveldb.get(key));
        initializeTablesFromItems(key, hit.items, sqldb);
      }
      sqldb.parallelize(async () => {
        for (let key of testKeys) {
          let hit = JSON.parse(await leveldb.get(key));
          parseItems(key, hit.items, sqldb);
        }
      });
    });
  })();
}