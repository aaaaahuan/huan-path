// Sidebar name search (Happy DOM): fuzzy filter, count badge, empty state, clear, IME, upload still reachable.
import fs from 'node:fs';import assert from 'node:assert/strict';import {Window} from '../work/browser-test/node_modules/happy-dom/lib/index.js';
const win=new Window({url:'http://127.0.0.1:8766/'});globalThis.window=win;globalThis.document=win.document;globalThis.location=win.location;globalThis.localStorage=win.localStorage;document.body.innerHTML=fs.readFileSync('app/ui/index.html','utf8');
const stages=[{key:'parse',name:'解析',status:'done',elapsed_seconds:1,detail:''}];
const job=(id,name,filename)=>({id,name,filename,status:'completed',stages,photo_count:0,house_count:0,preview_url:`/jobs/${id}/web/`,started_at:1792000000});
const jobs=[job('20261022-202757-e4b28f8962','桂林阳朔漓江精华线','guilin.kmz'),job('20261022-202157-50be9abb92','2026-03-14 杭州爱心线','hangzhou-love.kmz'),job('20261021-222421-be8fe509f3','2026-09-17 雨崩·尼农线','Yubeng.KMZ'),job('20261022-202357-bdb2c418ff','2026-04-25 南京紫金山','nanjing.kml')];
globalThis.fetch=async url=>({ok:true,json:async()=>url==='/api/jobs'?jobs:jobs.find(j=>url.endsWith(j.id))});
await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync('app/ui/upload.js')).toString('base64'));const tick=()=>new Promise(resolve=>setTimeout(resolve,20));await tick();
const $=s=>document.querySelector(s),names=()=>[...document.querySelectorAll('.work-card .work-name')].map(e=>e.textContent),input=$('#work-filter');
const type=value=>{input.value=value;input.dispatchEvent(new win.Event('input'))};
assert.equal($('#sidebar-new'),null,'sidebar 新建作品 removed');assert.equal(input.getAttribute('aria-label'),'按名称搜索作品');assert($('#work-filter-clear').hidden);assert.equal(names().length,4);assert.equal($('#work-count').textContent,'4');
type('杭州');assert.deepEqual(names(),['2026-03-14 杭州爱心线']);assert.equal($('#work-count').textContent,'1/4');assert(!$('#work-filter-clear').hidden);assert($('#work-search').classList.contains('filtering'));
type('雨崩');assert.deepEqual(names(),['2026-09-17 雨崩·尼农线']);
type('杭州线');assert.deepEqual(names(),['2026-03-14 杭州爱心线'],'characters in order');
type('  YUBENG ');assert.deepEqual(names(),['2026-09-17 雨崩·尼农线'],'case-insensitive, trims, matches filename');
type('ＧＵＩＬＩＮ');assert.deepEqual(names(),['桂林阳朔漓江精华线'],'full-width input normalised');
type('线');assert.deepEqual(names(),['桂林阳朔漓江精华线','2026-03-14 杭州爱心线','2026-09-17 雨崩·尼农线'],'original order kept within same rank');
type('紫金');assert.deepEqual(names(),['2026-04-25 南京紫金山']);
type('2026紫山');assert.deepEqual(names(),['2026-04-25 南京紫金山']);
type('西藏');assert.equal(names().length,0);assert.equal($('.library-empty').textContent,'没有名称匹配「西藏」的作品');assert.equal($('#work-count').textContent,'0/4');
$('#work-filter-clear').click();assert.equal(input.value,'');assert.equal(names().length,4);assert($('#work-filter-clear').hidden);assert(!$('#work-search').classList.contains('filtering'));
// IME: pinyin keystrokes during composition must not filter the list.
input.value='hang';input.dispatchEvent(new win.InputEvent('input',{isComposing:true}));assert.equal(names().length,4);input.value='杭';input.dispatchEvent(new win.Event('compositionend'));assert.deepEqual(names(),['2026-03-14 杭州爱心线']);
// Escape clears the query; list refreshes keep the filter.
const esc=new win.KeyboardEvent('keydown',{key:'Escape',bubbles:true});input.dispatchEvent(esc);assert.equal(input.value,'');assert.equal(names().length,4);
type('南京');await new Promise(r=>setTimeout(r,5100));assert.deepEqual(names(),['2026-04-25 南京紫金山'],'5 s refresh keeps filter');
// Selecting a filtered work works; upload stays reachable through the toolbar 「新建作品」 and the brand link.
document.querySelector('.work-card').click();await tick();assert(!$('#viewer-view').hidden);assert(!$('#new-work').hidden);$('#new-work').click();assert(!$('#upload-view').hidden);assert($('#drop'));
document.querySelector('.work-card').click();await tick();$('.brand').click();assert(!$('#upload-view').hidden);
// Collapsed rail: collapsing clears the filter; the magnifier reopens the sidebar.
assert.equal(input.value,'南京');$('#sidebar-toggle').click();assert($('#workspace').classList.contains('sidebar-collapsed'));assert.equal(input.value,'');assert.equal(names().length,4,'collapse clears filter');$('#work-search').click();assert(!$('#workspace').classList.contains('sidebar-collapsed'));
console.log({status:'passed',checks:24});win.dispatchEvent(new win.Event('pagehide'));await win.happyDOM.abort();
