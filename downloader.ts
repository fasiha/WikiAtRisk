import {Callbag, Factory, Operator} from 'callbag';
import {product} from 'cartesian-product-generator';
import {writeFileSync} from 'fs';
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

function myflatmap<T, U>(f: (value: T, index?: number, array?: T[]) => U, arr: T[]) {
  let ret: U[] = [];
  arr.forEach((v, i, arr) => ret = ret.concat(f(v, i, arr)));
  return ret;
}

let codes = new Set([...myflatmap(
    s => (s.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1).replace(/-(.)/g, (_, c) => c.toUpperCase())), URLS) ]);

function allArgsGenerator() {
  let editorTypes = 'anonymous,group-bot,name-bot,user'.split(',');
  let pageTypes = 'content,non-content'.split(',');
  let accessSites = 'desktop-site,mobile-site'.split(',');
  let accesses = 'desktop,mobile-app,mobile-web'.split(',');
  let agents = 'user,spider'.split(',');
  const converter = ([ editorType, pageType, accessSite, access, agent ]: string[]) => (
      { editorType, pageType, accessSite, access, agent });
  return pipe(fromIter(product(editorTypes, pageTypes, accessSites, accesses, agents)), map(converter));
}

async function fetchJSON(url: string) {
  const res = await fetch(url);
  if (res.status >= 400) { throw new Error(`HTTP status ${res.status} received from ${url}`); }
  return res.json();
}

function dashCaseToCamel(s: string) { return s.replace(/-(.)/g, (_, c) => c.toUpperCase()); }

function templateArgsToURL(urlTemplate: string, args: any) {
  const keys = (urlTemplate.match(/{[^}]+}/g) || []).map(s => s.slice(1, -1)).map(dashCaseToCamel);
  if (!keys.every(key => args.hasOwnProperty(key))) {
    const missing = keys.find(key => !args.hasOwnProperty(key));
    throw new Error(`${urlTemplate} not provided with "${missing}" key`);
  }
  let url = `${BASE_URL}${dashCaseToCamel(urlTemplate)}`;
  url = url.replace(/{[^}]+}/g, s => args[dashCaseToCamel(s.slice(1, -1))]);
  return url || fetchJSON(url);
}

function endpointYearArgsToURL(endpoint: string, year: number, args: any) {
  const keyRegExp = new RegExp(`/${endpoint}/`);
  const templates = URLS.filter(url => keyRegExp.test(url));
  if (templates.length !== 1) { throw new Error(`${templates.length} templates found to match endpoint ${endpoint}`); }
  const template = templates[0];
  args.start = `${year}0101`;
  args.end = `${year + 1}0101`;
  return templateArgsToURL(template, args);
}

function endpointYearProjectToData(endpoint: string, year: number, project: string) {
  const allArgs = allArgsGenerator();
  pipe(allArgs, throttle(1000), forEach((args: any) => {
    args.project = project;
    args.activityLevel = 'all-activity-levels';
    args.granularity = endpoint.indexOf('pageviews') >= 0 ? 'hourly' : 'daily';

    console.log(endpointYearArgsToURL(endpoint, year, args));
  }));
}

if (require.main === module) {
  (async function main() {
    // var yearly = await downloadEditedPagesDataHelper('en', 'user', 'content', 2017);
    // writeFileSync('yearly.json', JSON.stringify(yearly, null, 1));
    console.log(codes);
    endpointYearProjectToData('editors', 2017, 'en.wikipedia');
  })();
}