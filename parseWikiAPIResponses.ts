const level = require('level');
const db = level('./past-yearly-data');

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
    let raw = await db.get(
        "https://wikimedia.org/api/rest_v1/metrics/edited-pages/aggregate/en.wikipedia/anonymous/content/all-activity-levels/daily/20170101/20180101");
    let hit = JSON.parse(raw);
    // console.log(hit.items[0].results);
    const flatten1 = (arr: any[]) => arr.reduce((acc, x) => acc.concat(x), []);
    if (hit.items) {
      console.log(hit.items[0].results[0])
      console.log((
          hit.items ||
          []).map((item: any) => new Set(flatten1((item.results || []).map((result: any) => Object.keys(result))))));
    }
  })();
}