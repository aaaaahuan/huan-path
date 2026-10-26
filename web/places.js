// Preview-only OSM place-name labels (DOM overlay anchored at terrain height).
// Labels never modify printed geometry; greedy declutter keeps higher-rank places.
const CSS=`.place-labels{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:1}
.place-label{position:absolute;left:0;top:0;white-space:nowrap;color:#fbf7ea;font-weight:600;letter-spacing:.5px;text-shadow:0 0 3px #0b1517,0 0 6px #0b1517,0 1px 2px #000;will-change:transform;line-height:1}
.place-label::before{content:"";display:inline-block;width:5px;height:5px;border-radius:50%;background:#fbf7ea;box-shadow:0 0 0 1.5px #1a2a2c;margin-right:5px;vertical-align:middle}
.place-label.rank-1{color:#fff3c7}.place-label.rank-2{color:#fff6dc}.place-label.rank-4{font-weight:500;color:#eee9d8}.place-label.rank-5{font-weight:400;font-style:italic;color:#d6dccf}
.place-label.rank-5::before{width:3px;height:3px;background:#d6dccf}`;
// Terrain occlusion: march the anchor→camera ray over the preview heightfield (model mm space).
// Cheap enough for 400 labels on 626² grids; only re-run when the camera moves (throttled while moving).
export function makeOcclusion({size,grid,surfaceAt,maxZ,tolerance=.3,skip=1.5,stepCells=.5}){
 const cell=Math.min(size[0]/Math.max(1,grid[0]-1),size[1]/Math.max(1,grid[1]-1));
 return function occluded(ax,ay,az,cx,cy,cz){
  const dx=cx-ax,dy=cy-ay,dz=cz-az,horizontal=Math.hypot(dx,dy);
  if(horizontal<1e-9)return false;
  // Clip ray to the model footprint; beyond it there is no terrain.
  let tMax=1;
  if(dx>0)tMax=Math.min(tMax,(size[0]-ax)/dx);else if(dx<0)tMax=Math.min(tMax,-ax/dx);
  if(dy>0)tMax=Math.min(tMax,(size[1]-ay)/dy);else if(dy<0)tMax=Math.min(tMax,-ay/dy);
  if(dz>0)tMax=Math.min(tMax,(maxZ+tolerance-az)/dz);
  const step=stepCells*cell/horizontal;let t=skip*cell/horizontal;
  for(;t<=tMax;t+=step){
   const z=az+dz*t;if(dz<=0&&z<-1)break;
   if(z<surfaceAt(ax+dx*t,ay+dy*t)-tolerance)return true;
  }
  return false;
 };
}
// While orbiting, occlusion is refreshed at most this often; a final pass runs once the camera settles.
const THROTTLE_MS=120;
export async function initPlaceLabels({THREE,meta,scene,renderer,surfaceAt,mesh}){
 const url=meta.preview_layers.places;
 const response=await fetch(url);if(!response.ok)throw Error(`地名图层加载失败 ${url}`);
 const {labels,styles}=await response.json();
 if(!document.querySelector('#place-label-style')){const style=document.createElement('style');style.id='place-label-style';style.textContent=CSS;document.head.append(style)}
 // Full-viewport overlay (the viewer canvas fills the window), so no per-frame sizing is needed.
 const host=document.createElement('div');host.className='place-labels';host.setAttribute('aria-hidden','true');
 renderer.domElement.after(host);
 const lift=meta.settlements?.places?.lift_mm??.6;
 const items=labels.map(row=>{
  const el=document.createElement('div');el.className=`place-label rank-${row.rank}`;el.textContent=row.name;
  const font=styles?.[row.kind]?.font_px||12;el.style.fontSize=font+'px';el.title=row.name_source?`${row.name}（${row.name_source}）`:row.name;
  el.style.display='none';host.append(el);
  // Approximate box avoids layout reads per frame: CJK ≈ 1em, Latin ≈ .6em.
  const width=[...row.name].reduce((s,ch)=>s+(ch.charCodeAt(0)>255?1:.6),0)*font+10;
  return {row,el,width,height:font+4,shown:false,hidden:false,world:new THREE.Vector3()};
 });
 let visible=true,dirty=true,last=null,lastOcclusion=-Infinity,occlusionStale=true,occluded=null;const v=new THREE.Vector3(),eye=new THREE.Vector3(),inverse=new THREE.Matrix4();
 const grid=meta.preview_layers.grid,size=meta.size;
 function anchor(){
  for(const item of items){const {x_mm:x,y_mm:y}=item.row;item.world.set(x,y,surfaceAt(x,y)+lift)}
  // Highest point of the current preview mesh caps the ray march (rays above it cannot hit terrain).
  const geometry=mesh.geometry;if(!geometry.boundingBox)geometry.computeBoundingBox();
  occluded=makeOcclusion({size,grid,surfaceAt,maxZ:geometry.boundingBox.max.z});
  occlusionStale=true;
 }
 anchor();
 function runOcclusion(camera){
  inverse.copy(scene.matrixWorld).invert();eye.setFromMatrixPosition(camera.matrixWorld).applyMatrix4(inverse);
  let count=0;
  for(const item of items){const w=item.world;item.hidden=occluded(w.x,w.y,w.z,eye.x,eye.y,eye.z);if(item.hidden)count++}
  api.occluded=count;lastOcclusion=performance.now();occlusionStale=false;
 }
 function update(camera){
  if(!visible)return;
  const rect=renderer.domElement.getBoundingClientRect();camera.updateMatrixWorld();
  const key=[...camera.matrixWorld.elements,camera.zoom||1,camera.fov||0,rect.width,rect.height];
  const moved=dirty||!last||!key.every((x,i)=>Math.abs(x-last[i])<1e-4);
  if(moved)occlusionStale=true;
  const doOcclusion=occlusionStale&&(!moved||performance.now()-lastOcclusion>=THROTTLE_MS);
  if(!moved&&!doOcclusion)return;last=key;dirty=false;
  if(doOcclusion){const t0=performance.now();runOcclusion(camera);api.occlusionMs=performance.now()-t0}
  const taken=[];
  for(const item of items){
   v.copy(item.world).applyMatrix4(scene.matrixWorld).project(camera);
   let show=!item.hidden&&v.z>-1&&v.z<1&&Math.abs(v.x)<=1.05&&Math.abs(v.y)<=1.05;
   const px=(v.x+1)/2*rect.width,py=(1-v.y)/2*rect.height;
   const box=[px-3,py-item.height/2-1,px+item.width,py+item.height/2+1];
   if(show)for(const t of taken){if(box[0]<t[2]&&box[2]>t[0]&&box[1]<t[3]&&box[3]>t[1]){show=false;break}}
   if(show){taken.push(box);item.el.style.transform=`translate(${(px-3).toFixed(1)}px,${(py-item.height/2).toFixed(1)}px)`}
   if(show!==item.shown){item.el.style.display=show?'block':'none';item.shown=show}
  }
  api.shown=taken.length;
 }
 const api={update,count:items.length,shown:0,occluded:0,occlusionMs:0,
  setVisible(on){visible=!!on;host.style.display=visible?'':'none';dirty=true},
  invalidate(){anchor();dirty=true}};
 return api;
}
