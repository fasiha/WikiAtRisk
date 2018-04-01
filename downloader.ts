import {existsSync, readFileSync, writeFileSync} from 'fs';
import fetch from 'node-fetch';
const { pipe, fromIter, concat, filter, map, forEach } = require('callbag-basics');
const throttle = require('callbag-throttle');
const filterPromise = require('callbag-filter-promise');
const flatten = require('callbag-flatten');
const cartesian = require('callbag-cartesian-product');
const flatMap = require('callbag-flat-map-operator');
const dashCaseToCamel: (s: string) => string = require('camelcase');

const BASE_URL = 'https://wikimedia.org/api/rest_v1';
const MINIMUM_THROTTLE_DELAY_MS = 530; // 15 -> 66 requests per second

import {URLS, defaultCombinations} from './endpoints';

// These types aren't used but are helpful to refer to. They're extracted from https://wikimedia.org/api/rest_v1/ also
type EditorType = 'anonymous'|'group-bot'|'name-bot'|'user'|'all-editor-types';
type PageType = 'content'|'non-content'|'all-page-types';
type AccessSite = 'desktop-site'|'mobile-site'|'all-sites';
type Access = 'desktop'|'mobile-app'|'mobile-web'|'all-access';
type Agent = 'user'|'spider'|'all-agents';

function urlTemplateToKeys(template: string) {
  return (template.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1)).map(s => dashCaseToCamel(s));
}

function templateArgsToURL(urlTemplate: string, args: any) {
  const keys = urlTemplateToKeys(urlTemplate);
  if (!keys.every(key => args.hasOwnProperty(key))) {
    const missing = keys.find(key => !args.hasOwnProperty(key));
    throw new Error(`${urlTemplate} not provided with "${missing}" key`);
  }
  return `${BASE_URL}${urlTemplate}`.replace(/{[^}]+}/g, s => args[dashCaseToCamel(s.slice(1, -1))]);
}

function keysToCallbag(keysNeeded: string[]) {
  if (!keysNeeded.every(key => defaultCombinations[key])) {
    throw new Error(
        'Key could not be filled in automatically: ' + keysNeeded.find((key: string) => !defaultCombinations[key]));
  }
  if (keysNeeded.length === 0) { return fromIter([ [ {} ] ]); }
  return map((args: any[]) => args.map((arg, i) => {
    let ret: any = {};
    ret[keysNeeded[i]] = arg;
    return ret;
  }))(cartesian(...keysNeeded.map(key => fromIter(defaultCombinations[key]))));
}

function endpointYearProjectToURLs(endpoint: string, year: number, project: string) {
  const keyRegExp = new RegExp(`/${endpoint}/`);
  const templates = URLS.filter(url => keyRegExp.test(url));
  if (templates.length !== 1) { throw new Error(`${templates.length} templates found to match endpoint ${endpoint}`); }
  const template = templates[0];

  const allKeysNeeded = urlTemplateToKeys(template);

  const granularity = 'daily';
  const start = `${year}0101`;
  const end = `${year + 1}0101`;
  // const granularity = endpoint.indexOf('pageviews') >= 0 ? 'hourly' : 'daily'; // FIXME
  if (granularity === ('hourly' as any)) {
    throw new Error('Hourly might deliver incomplete (5000 element only) set, with a next field.');
  }

  let baseArgs = { project, granularity, start, end };
  let baseKeys = new Set(Object.keys(baseArgs));
  let combinationKeysNeeded = allKeysNeeded.filter(needed => !baseKeys.has(needed));
  let combinationBag = keysToCallbag(combinationKeysNeeded);

  if (endpoint.indexOf('top-by-edits') >= 0) {
    // The top-by-edits endpoint returns 1.2 MB JSON payloads for annual data, and frequently errors out. Make this
    // monthly to see if this is more reliable.
    const leftpad = (x: number) => x < 10 ? '0' + x : x;
    const monthsCallbag = fromIter(Array.from(Array(12), (_, i: number) => ({
      start : `${year}${leftpad(i + 1)}01`,
      end : i === 11 ? `${year + 1}0101` : `${year}${leftpad(i + 1 + 1)}01`
    })));
    combinationBag = flatMap(() => monthsCallbag, (arr: any[], month: any) => arr.concat(month))(combinationBag);
  }
  let allArgs = map((args: any) => Object.assign(baseArgs, ...args))(combinationBag);
  const mapper = map((args: any) => templateArgsToURL(template, args));
  return mapper(allArgs);
}

if (require.main === module) {
  function myflatmap<T, U>(f: (value: T, index?: number, array?: T[]) => U, arr: T[]) {
    let ret: U[] = [];
    arr.forEach((v, i, arr) => ret = ret.concat(f(v, i, arr)));
    return ret;
  }
  function iterCartesian(...args: any[]) { return cartesian(...args.map(fromIter) as any); }
  (async function main() {
    let codes = new Set([...myflatmap(
        s => (s.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1).replace(/-(.)/g, (_, c) => c.toUpperCase())), URLS) ]);
    // console.log(codes);

    const level = require('level');
    const db = level('./past-yearly-data');
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
    const fetchOptions = { headers : { 'User-Agent' : 'See https://github.com/fasiha/wikiatrisk' } };

    // 2001-2019 (18 years), nine endpoints, fifty to a hundred wikipedias
    const shortUrls = URLS.map(s => s.slice(0, s.indexOf('{')).split('/').slice(2, 4).filter(x => x.length).join('/'));
    const years = [...range(2001, 2018) ].reverse();

    const parameters = iterCartesian(years, shortUrls, wikilangsdata.slice(0, 50).map(o => o.prefix + '.wikipedia'));
    pipe(
        parameters,
        flatMap(([ year, endpoint, project ]: any) => endpointYearProjectToURLs(endpoint, year, project)),
        // forEach((x: any) => console.log(x)),
        filterPromise(async (url: string) => {
          try {
            await db.get(url);
            return false;
          } catch (err) {
            if (err.type !== 'NotFoundError') { throw err; }
          }
          return true;
        }),
        throttle(MINIMUM_THROTTLE_DELAY_MS),
        forEach(async (url: string) => {
          console.log("asking…");
          db.put(url, await fetch(url, fetchOptions).then(res => res.text()));
          console.log(url);
        }),
    );
  })();
}
