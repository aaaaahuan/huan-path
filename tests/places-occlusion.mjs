// Run: node tests/places-occlusion.mjs (from repo root). Preview-only label occlusion checks.
import fs from 'node:fs';import assert from 'node:assert/strict';
import {Window} from '../work/browser-test/node_modules/happy-dom/lib/index.js';
import * as THREE from '../web/vendor/three.module.js';
const {makeOcclusion,initPlaceLabels}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync('web/places.js','utf8')).toString('base64'));
// 100×100 mm plate, flat at z=1 with a 20 mm ridge along x=50.
const size=[100,100],grid=[313,313];
const surfaceAt=(x,y)=>1+(Math.abs(x-50)<3?20*(1-Math.abs(x-50)/3):0);
const occ=makeOcclusion({size,grid,surfaceAt,maxZ:21});
const lift=.6;
assert.equal(occ(20,50,1+lift,80,50,10),true,'label behind ridge is hidden');
assert.equal(occ(20,50,1+lift,-30,50,10),false,'label in front of ridge is visible');
assert.equal(occ(20,50,1+lift,80,50,200),false,'steep view over ridge sees the label');
assert.equal(occ(50,50,21+lift,90,50,22),false,'label on ridge top is not self-occluded');
assert.equal(occ(70,50,1+lift,70,50,100),false,'top-down view never occludes');
// Grazing view across flat ground: tolerance prevents false hiding.
assert.equal(occ(5,5,1+lift,40,95,1.7),false,'grazing over flat ground stays visible');
// Perf: 400 labels × worst-case rays on a 626² grid.
const big=makeOcclusion({size:[200,200],grid:[626,626],surfaceAt:(x,y)=>1+Math.sin(x/7)*Math.cos(y/9)*3+3,maxZ:8});
let t0=performance.now();for(let k=0;k<400;k++)big(k%200,(k*37)%200,7.6,-100,-80,7.7);const ms=performance.now()-t0;
const flat=makeOcclusion({size:[200,200],grid:[626,626],surfaceAt:()=>1,maxZ:8});
let t1=performance.now();for(let k=0;k<400;k++)assert.equal(flat(195,(k*37)%200,1.6,-300,100,7.9),false);const ms2=performance.now()-t1;
console.log(`occlusion 400 full-length unoccluded rays on 626² grid: ${ms2.toFixed(1)} ms`);assert(ms2<300);
console.log(`occlusion 400 grazing rays on 626² grid: ${ms.toFixed(1)} ms`);assert(ms<200);
// Integration: hidden labels are skipped by declutter and reported.
const win=new Window({width:800,height:600});globalThis.window=win;globalThis.document=win.document;globalThis.performance??=win.performance;
const labels=[{name:'山后村',kind:'village',rank:3,x_mm:20,y_mm:50},{name:'山前村',kind:'village',rank:3,x_mm:80,y_mm:50}];
globalThis.fetch=async()=>({ok:true,json:async()=>({labels,styles:{village:{font_px:13}}})});
const canvas=document.createElement('canvas');document.body.append(canvas);canvas.getBoundingClientRect=()=>({width:800,height:600,left:0,top:0});
const scene=new THREE.Scene();scene.updateMatrixWorld();
const meta={size,preview_layers:{grid,places:'places.json'},settlements:{places:{lift_mm:lift}}};
// Ray-march cap comes from the preview mesh bounding box (ridge top = 21 mm).
const mesh={geometry:{boundingBox:{max:{z:21}}}};
const api=await initPlaceLabels({THREE,meta,scene,renderer:{domElement:canvas},surfaceAt,mesh});
const camera=new THREE.PerspectiveCamera(36,800/600,.1,3000);camera.up.set(0,0,1);camera.position.set(130,50,12);camera.lookAt(50,50,1);camera.updateMatrixWorld();
api.update(camera);
const state=Object.fromEntries([...document.querySelectorAll('.place-label')].map(e=>[e.textContent,e.style.display]));
assert.equal(api.occluded,1);assert.equal(state['山后村'],'none');assert.equal(state['山前村'],'block');
// Hidden flags must match makeOcclusion evaluated directly from the same eye point.
const eye=camera.position;assert.deepEqual(labels.map(l=>occ(l.x_mm,l.y_mm,surfaceAt(l.x_mm,l.y_mm)+lift,eye.x,eye.y,eye.z)),[true,false]);
// Orbit to the other side: occlusion is recomputed (stale flags would keep 山后村 hidden).
camera.position.set(-30,50,12);camera.lookAt(50,50,1);camera.updateMatrixWorld();api.update(camera);api.update(camera);  // 2nd call = settled-camera pass
assert.deepEqual(labels.map(l=>occ(l.x_mm,l.y_mm,surfaceAt(l.x_mm,l.y_mm)+lift,-30,50,12)),[false,true]);
assert.equal(api.occluded,1);assert.equal(document.querySelectorAll('.place-label')[0].style.display,'block','visible again from the other side');assert.equal(document.querySelectorAll('.place-label')[1].style.display,'none');
console.log('places occlusion: OK');
