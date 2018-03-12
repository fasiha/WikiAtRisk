const throttle = require('callbag-throttle');
const level = require('level');
const db = level('./past-yearly-data');
const { pipe, filter, forEach } = require('callbag-basics');
const fromStream = require('callbag-from-stream');
if (require.main === module) {
  const command = process.argv[2];
  commands = {
    ls : {
      f : (async () => { pipe(fromStream(db.createReadStream()), forEach(x => console.log(x.key + '=>' + x.value))); })
    },
    rmalllll : { f : (async () => { pipe(fromStream(db.createKeyStream()), forEach(key => db.del(key))); }) },
    keys : { f : (async () => { pipe(fromStream(db.createKeyStream()), forEach(x => console.log('KEY=' + x))); }) },
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
    }
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