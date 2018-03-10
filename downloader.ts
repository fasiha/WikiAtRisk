import {Callbag, Factory, Operator} from 'callbag';
import {product} from 'cartesian-product-generator';
import {existsSync, readFileSync, writeFileSync} from 'fs';
import fetch from 'node-fetch';
const { forEach, fromIter, take, map, pipe } = require('callbag-basics');
const throttle: Operator = require('callbag-throttle');

const BASE_URL = 'https://wikimedia.org/api/rest_v1';

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

function allArgsGenerator() {
  const editorTypes = 'anonymous,group-bot,name-bot,user'.split(',');
  const pageTypes = 'content,non-content'.split(',');
  const accessSites = 'desktop-site,mobile-site'.split(',');
  const accesses = 'desktop,mobile-app,mobile-web'.split(',');
  const agents = 'user,spider'.split(',');
  const converter = ([ editorType, pageType, accessSite, access, agent ]: string[]) => (
      { editorType, pageType, accessSite, access, agent });
  return pipe(fromIter(product(editorTypes, pageTypes, accessSites, accesses, agents)), map(converter));
}

function dashCaseToCamel(s: string) { return s.replace(/-(.)/g, (_, c) => c.toUpperCase()); }

function templateArgsToURL(urlTemplate: string, args: any) {
  const keys = (urlTemplate.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1)).map(dashCaseToCamel);
  if (!keys.every(key => args.hasOwnProperty(key))) {
    const missing = keys.find(key => !args.hasOwnProperty(key));
    throw new Error(`${urlTemplate} not provided with "${missing}" key`);
  }
  return `${BASE_URL}${urlTemplate}`.replace(/{[^}]+}/g, s => args[dashCaseToCamel(s.slice(1, -1))]);
}

function endpointYearArgsToURL(endpoint: string, year: number, args: any) {
  const keyRegExp = new RegExp(`/${endpoint}/`);
  const templates = URLS.filter(url => keyRegExp.test(url));
  if (templates.length !== 1) { throw new Error(`${templates.length} templates found to match endpoint ${endpoint}`); }
  const template = templates[0];
  args.start = `${year}0101`;
  args.end = `${year + 1}0101`;
  if (args.granularity === 'hourly') {
    args.start += '00';
    args.end += '00';
    throw new Error('Hourly might deliver incomplete (5000 element only) set, with a next field.');
  }
  return templateArgsToURL(template, args);
}

function endpointYearProjectToURLs(endpoint: string, year: number, project: string) {
  const allArgs = allArgsGenerator();
  return pipe(allArgs, map((args: any) => {
    args.project = project;
    args.activityLevel = 'all-activity-levels';
    // args.granularity = endpoint.indexOf('pageviews') >= 0 ? 'hourly' : 'daily'; // FIXME
    args.granularity = 'daily';
    return endpointYearArgsToURL(endpoint, year, args);
  }));
}

if (require.main === module) {
  function myflatmap<T, U>(f: (value: T, index?: number, array?: T[]) => U, arr: T[]) {
    let ret: U[] = [];
    arr.forEach((v, i, arr) => ret = ret.concat(f(v, i, arr)));
    return ret;
  }
  async function fetchJSON(url: string) {
    const res = await fetch(url);
    if (res.status >= 400) { throw new Error(`HTTP status ${res.status} received from ${url}`); }
    return res.json();
  }
  (async function main() {
    let codes = new Set([...myflatmap(
        s => (s.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1).replace(/-(.)/g, (_, c) => c.toUpperCase())), URLS) ]);
    console.log(codes);

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

    // 2001-2019 (18 years), nine endpoints, fifty to a hundred wikipedias
    const shortUrls = URLS.map(s => s.slice(0, s.indexOf('{')).split('/').slice(2, 4).filter(x => x.length).join('/'));
    const years = [...range(2001, 2018) ].reverse();
    const outerProduct = product(years, shortUrls, wikilangsdata.slice(0, 50).map(o => o.prefix + '.wikipedia'));
    for (let [year, endpoint, project] of outerProduct) {
      pipe(endpointYearProjectToURLs(endpoint, year, project), forEach(async (url: string) => {
        console.log(url);
        // const exists = await db.get(url);
        // if (!exists) { db.put(url, await fetchJSON(url)); }
      }));
    }
  })();
}