const throttle = require('callbag-throttle');
const level = require('level');
const db = level('./past-yearly-data');
const { pipe, forEach } = require('callbag-basics');
const fromStream = require('callbag-from-stream');
if (require.main === module) {
  const command = process.argv[2];
  commands = {
    ls : {
      f : (async () => {
        var stream = db.createReadStream();
        pipe(fromStream(stream), forEach(x => console.log(x.key + '=>' + JSON.stringify(x.value))));
      })
    },
    rmalllll : {
      f : (async () => {
        var stream = db.createReadStream();
        pipe(fromStream(stream), forEach(({ key, value }) => db.del(key)));
      })
    },
    keys : {
      f : (async () => {
        var stream = db.createReadStream();
        pipe(fromStream(stream), forEach(x => console.log('KEY=' + x.key)));
      })
    },
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