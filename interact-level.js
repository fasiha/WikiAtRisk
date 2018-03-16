const throttle = require('callbag-throttle');
const level = require('level');
const db = level('./past-yearly-data');
const { pipe, filter, scan, take, map, forEach } = require('callbag-basics');
const fromStream = require('callbag-from-stream');
const last = require('callbag-last');
if (require.main === module) {
  const command = process.argv[2];
  commands = {
    ls : {
      f : (async () => { pipe(fromStream(db.createReadStream()), forEach(x => console.log(x.key + '=>' + x.value))); })
    },
    rmalllll : { f : (async () => { pipe(fromStream(db.createKeyStream()), forEach(key => db.del(key))); }) },
    keys : { f : (async () => { pipe(fromStream(db.createKeyStream()), forEach(x => console.log(x))); }) },
    get : {
      f : (async () => {
        let key = process.argv[3];
        if (!key) {
          console.error('Need key');
          return;
        }
        console.log(key + '=>' + await db.get(key));
      })
    },
    rm : {
      f : (async () => {
        let key = process.argv[3];
        if (!key) {
          console.error('Need key');
          return;
        }
        db.del(key);
      })
    },
    errs : {
      f : (async () => { pipe(
               fromStream(db.createReadStream()),
               filter(({ value }) => (/error/).test(value)),
               forEach(x => console.log(x.key + '=>' + x.value)),
               ) })
    },
    resultsKeys : {
      f : (() => {
        pipe(
            fromStream(db.createValueStream()),
            // take(100),
            map(text => JSON.parse(text)),
            filter(res => res.items && res.items[0] && res.items[0].results),
            map(res => Object.keys(res.items[0].results[0])),
            scan(
                (acc, curr) => {
                  curr.forEach(k => acc.add(k));
                  return acc;
                },
                new Set()),
            last(),
            forEach(x => console.log(x)),
        );
      })
    },
  };
  const showCommands = () => console.log('Options: ' + Object.keys(commands).join(', '));
  if (command) {
    let hit = commands[command];
    if (hit) {
      (hit.f)();
    } else {
      console.error('Bad command')
      showCommands();
    }
  } else {
    showCommands();
  }
}