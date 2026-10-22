import fs from 'node:fs';import assert from 'node:assert/strict';import {Window} from '../work/browser-test/node_modules/happy-dom/lib/index.js';import * as THREE from '../web/vendor/three.module.js';
const jobsRoot=process.env.HUAN_PATH_JOBS_DIR || 'jobs';
const results=fs.readdirSync(jobsRoot).filter(id=>fs.existsSync(`${jobsRoot}/${id}/web/metadata.json`)).map(job_id=>({job_id}));
const encode=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const product=await import(encode(fs.readFileSync('web/product-info.js','utf8'))),photos=await import(encode(fs.readFileSync('web/photos.js','utf8')));
const pinUrl=encode(fs.readFileSync('web/pin-houses.js','utf8'));const feature=await import(encode(fs.readFileSync('web/features.js','utf8').replace("'./pin-houses.js'",JSON.stringify(pinUrl))));
const records=[];
for(const test of results){
 const dir=`${jobsRoot}/${test.job_id}/web/`,meta=JSON.parse(fs.readFileSync(dir+'metadata.json')),window=new Window({url:`http://127.0.0.1:8766/jobs/${test.job_id}/web/`});globalThis.window=window;globalThis.document=window.document;globalThis.location=window.location;globalThis.innerHeight=1000;globalThis.innerWidth=1440;document.body.innerHTML=fs.readFileSync(dir+'index.html','utf8');
 globalThis.fetch=async url=>{if(url.startsWith('/api/jobs/'))return {ok:true,json:async()=>JSON.parse(fs.readFileSync(`${jobsRoot}/${test.job_id}/data/photo_houses.json`))};const b=fs.readFileSync(dir+url.replace('./',''));return {ok:true,arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),json:async()=>JSON.parse(b)}};
 assert.equal(document.querySelector('footer'),null);const source=[...document.querySelectorAll('details')].find(d=>d.querySelector('summary').textContent==='数据来源');assert(source&&!source.open);assert(source.textContent.includes('OpenStreetMap')&&source.textContent.includes('WorldCover')&&source.textContent.includes('DLR'));
 product.initProductInfo(meta);const panelToggle=document.querySelector('#panel-toggle');assert.equal(panelToggle.getAttribute('aria-expanded'),'true');panelToggle.click();assert(document.querySelector('#panel-content').hidden);assert.equal(panelToggle.getAttribute('aria-expanded'),'false');assert.equal(window.localStorage.getItem('trail:model-panel-collapsed'),'true');panelToggle.click();assert(!document.querySelector('#panel-content').hidden);assert.equal(document.querySelector('#route-title').textContent,meta.route_info.name);if(meta.route_info.date)assert(document.querySelector('#route-subtitle').textContent.includes(meta.route_info.date));assert.equal(document.querySelector('#route-distance').textContent,meta.route_info.recorded_distance_km.toFixed(2));assert(document.querySelector('a[download][href$=".stl"]').getAttribute('href').endsWith('terrain.stl'));
 function data(name,Type){const b=fs.readFileSync(dir+name);return new Type(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength))}
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(data('vertices.bin',Float32Array),3));geo.setIndex(new THREE.BufferAttribute(data('faces.bin',Uint32Array),1));const scene=new THREE.Scene(),mesh=new THREE.Mesh(geo.toNonIndexed(),new THREE.MeshBasicMaterial());
 const controls=await feature.initFeatureControls({THREE,geo,mesh,scene,meta});assert.equal(document.querySelectorAll('#feature-switches button').length,7);const scaleButton=document.querySelector('[data-feature="elevation_scale"]');if(window.featureStatus.available.elevation_scale){assert(!scaleButton.disabled);scaleButton.click();assert.equal(scene.children[1].visible,false);scaleButton.click();assert.equal(scene.children[1].visible,true)}else{assert(scaleButton.disabled);assert.equal(scene.children[1].visible,false)};
 const roadButton=document.querySelector('[data-feature="roads"]');
 if(meta.roads?.count){
  const group=scene.children[2];assert(group.children.length>0);assert(group.visible);
  for(const road of group.children){const v=road.geometry.attributes.position;for(let i=0;i<v.count;i+=37)assert(Math.abs(v.getZ(i)-controls.surfaceAt(v.getX(i),v.getY(i))-meta.roads.lift_mm)<1e-4)}
  roadButton.click();assert(!group.visible);roadButton.click();assert(group.visible);
  document.querySelector('[data-feature="forest"]').click();
  for(const road of group.children){const v=road.geometry.attributes.position;for(let i=0;i<v.count;i+=37)assert(Math.abs(v.getZ(i)-controls.surfaceAt(v.getX(i),v.getY(i))-meta.roads.lift_mm)<1e-4)}
 }else assert(roadButton.disabled);
 if(meta.photos.total){
  window.HTMLCanvasElement.prototype.getContext=()=>({beginPath(){},arc(){},fill(){},stroke(){},fillText(){}});
  const canvas=document.createElement('canvas');canvas.getBoundingClientRect=()=>({left:0,top:0,width:1440,height:1000});const renderer={domElement:canvas};const camera=new THREE.PerspectiveCamera();camera.position.set(100,-100,200);const orbit=new THREE.EventDispatcher();orbit.autoRotate=false;const dialog=document.querySelector('#photo-dialog');dialog.showModal=()=>{dialog.open=true};document.querySelector('#houses-dialog').showModal=()=>{document.querySelector('#houses-dialog').open=true};
  await photos.initPhotoLayer({THREE,scene,camera,renderer,controls:orbit,terrain:mesh,meta,surfaceAt:controls.surfaceAt});assert.equal(window.photoStatus.markers,28);assert.equal(document.querySelectorAll('.photo-card').length,28);document.querySelector('.photo-card').click();assert(dialog.open);assert(document.querySelector('#photo-title').textContent);if(meta.house_detection==='manual')assert(document.querySelector('#photo-source').textContent.includes('不是同一次'));document.querySelector('#photos-toggle').click();assert(!window.photoStatus.visible);
  await document.querySelector('#edit-houses').onclick();assert.equal(document.querySelectorAll('.house-row').length,28);
 }
 records.push({job_id:meta.job_id,name:meta.route_info.name,checks:['dynamic route metadata and downloads','folded attribution with no footer','7 feature controls, roads draping/toggle and scale visibility',meta.photos.total?'28 local photo markers/list/modal and editable house table':'no photo layer advertised']});window.happyDOM.abort();
}
fs.writeFileSync('work/upload-ui-validation.json',JSON.stringify({status:'passed',scope:'Happy DOM and Three.js geometry; no WebGL screenshot',results:records},null,2));console.log(records);
