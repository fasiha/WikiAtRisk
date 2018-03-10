import {Callbag, Factory, Operator} from 'callbag';
import {product} from 'cartesian-product-generator';
import {existsSync, readFileSync, writeFileSync} from 'fs';
import fetch from 'node-fetch';
const { pipe, fromIter, concat, filter, map, forEach } = require('callbag-basics');
const throttle: Operator = require('callbag-throttle');

const BASE_URL = 'https://wikimedia.org/api/rest_v1';
const MINIMUM_THROTTLE_DELAY_MS = 1000; // 15 -> 66 requests per second

type EditorType = 'anonymous'|'group-bot'|'name-bot'|'user'|'all-editor-types';
type PageType = 'content'|'non-content'|'all-page-types';
type AccessSite = 'desktop-site'|'mobile-site'|'all-sites';
type Access = 'desktop'|'mobile-app'|'mobile-web'|'all-access';
type Agent = 'user'|'spider'|'all-agents';

const URLS = [
  '/metrics/edited-pages/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}',
  '/metrics/edits/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
  '/metrics/edited-pages/new/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
  '/metrics/editors/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}',
  '/metrics/registered-users/new/{project}/{granularity}/{start}/{end}',
  '/metrics/bytes-difference/net/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
  '/metrics/bytes-difference/absolute/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
  '/metrics/unique-devices/{project}/{access-site}/{granularity}/{start}/{end}',
  '/metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}',
];

function allArgsGenerator(keysWanted: string[]) {
  const all: any = {
    editorType : 'anonymous,group-bot,name-bot,user'.split(','),
    pageType : 'content,non-content'.split(','),
    accessSite : 'desktop-site,mobile-site'.split(','),
    access : 'desktop,mobile-app,mobile-web'.split(','),
    agent : 'user,spider'.split(',')
  };
  if (!keysWanted.every((key: string) => all[key])) {
    throw new Error('Keys not found to build arguments generator:' + keysWanted.find((key: string) => !all[key]));
  }
  const results = keysWanted.map(key => all[key]);
  const convertArrayToObj = (args: string[]) => {
    let o: any = {};
    args.forEach((arg, i) => o[keysWanted[i]] = arg);
    return o;
  };
  return (map(convertArrayToObj))(fromIter(product(...results)));
}

function dashCaseToCamel(s: string) { return s.replace(/-(.)/g, (_, c) => c.toUpperCase()); }

function urlTemplateToKeys(template: string) {
  return (template.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1)).map(dashCaseToCamel);
}

function templateArgsToURL(urlTemplate: string, args: any) {
  const keys = urlTemplateToKeys(urlTemplate);
  if (!keys.every(key => args.hasOwnProperty(key))) {
    const missing = keys.find(key => !args.hasOwnProperty(key));
    throw new Error(`${urlTemplate} not provided with "${missing}" key`);
  }
  return `${BASE_URL}${urlTemplate}`.replace(/{[^}]+}/g, s => args[dashCaseToCamel(s.slice(1, -1))]);
}

function endpointYearProjectToURLs(endpoint: string, year: number, project: string) {
  const keyRegExp = new RegExp(`/${endpoint}/`);
  const templates = URLS.filter(url => keyRegExp.test(url));
  if (templates.length !== 1) { throw new Error(`${templates.length} templates found to match endpoint ${endpoint}`); }
  const template = templates[0];

  const keysNeeded = urlTemplateToKeys(template);

  let start = `${year}0101`;
  let end = `${year + 1}0101`;
  const activityLevel = 'all-activity-levels';
  const granularity = 'daily';
  // const granularity = endpoint.indexOf('pageviews') >= 0 ? 'hourly' : 'daily'; // FIXME
  if (granularity === ('hourly' as any)) {
    start += '00';
    end += '00';
    throw new Error('Hourly might deliver incomplete (5000 element only) set, with a next field.');
  }

  let baseArgs = { project, activityLevel, granularity, start, end };
  let baseKeys = new Set(Object.keys(baseArgs));
  const allArgs = allArgsGenerator(keysNeeded.filter(needed => !baseKeys.has(needed)));
  const mapper = map((args: any) => templateArgsToURL(template, Object.assign(baseArgs, args)));
  return mapper(allArgs);
}

if (require.main === module) {
  function myflatmap<T, U>(f: (value: T, index?: number, array?: T[]) => U, arr: T[]) {
    let ret: U[] = [];
    arr.forEach((v, i, arr) => ret = ret.concat(f(v, i, arr)));
    return ret;
  }
  async function fetchJSON(url: string) {
    let res: any;
    // try {
    res = await fetch(url);
    // } catch (e) {
    // console.error(e);
    // process.exit();
    // }
    if (res.status >= 400) { throw new Error(`HTTP status ${res.status} received from ${url}`); }
    return res.json();
  }
  (async function main() {
    let codes = new Set([...myflatmap(
        s => (s.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1).replace(/-(.)/g, (_, c) => c.toUpperCase())), URLS) ]);
    // console.log(codes);

    const level = require('level');
    const db
        = level('./past-yearly-data', { cacheSize : 8 * 1024 * 1024 * 128, writeBufferSize : 4 * 1024 * 1024 * 128 });
    const range = require('range-generator');

    const WIKILANGSFILE = 'wikilangs.json';
    let wikilangsdata: any[];
    if (existsSync(WIKILANGSFILE)) {
      wikilangsdata = JSON.parse(readFileSync(WIKILANGSFILE, 'utf8'));
    } else {
      const wikilangs = require('wikipedia-languages');
      wikilangsdata = await wikilangs();
      writeFileSync(WIKILANGSFILE, JSON.stringify(wikilangsdata));
    }
    wikilangsdata.sort((a, b) => b.activeusers - a.activeusers);

    // 2001-2019 (18 years), nine endpoints, fifty to a hundred wikipedias
    const shortUrls = URLS.map(s => s.slice(0, s.indexOf('{')).split('/').slice(2, 4).filter(x => x.length).join('/'));
    const years = [...range(2001, 2018) ].reverse();

    // const outerProduct = product(years, shortUrls, wikilangsdata.slice(0, 50).map(o => o.prefix + '.wikipedia'));
    const outerProduct = product([ 2016, 2015, 2014, 2013 ], [ 'edits' ], [ 'en.wikipedia' ]);
    const sources = concat(...[...outerProduct].map(
        ([ year, endpoint, project ]: any) => endpointYearProjectToURLs(endpoint, year, project)));
    pipe(
        sources,
        throttle(MINIMUM_THROTTLE_DELAY_MS),
        // will throttle saved data too :(!!!)
        forEach(async (url: string) => {
          try {
            const exists = await db.get(url);
          } catch (err) {
            if (err.type === 'NotFoundError') {
              console.log(url);
              // db.put(url, JSON.stringify(await fetchJSON(url)));
            } else {
              throw err;
            }
          }
        }),
    );
  })();
}
/*
0.2 s to list 96 URLs to hit (one endpoint), no throttle
1.9 s to list, with 15 ms delay
*/