import {loadPinHouse} from './pin-houses.js';
// Reconstruct the same heightfield/material order used by feature_engine.compose.
export function composePreview({base,classes,forest,water,houses,distance,routeGap},state){
 const n=base.length,z=new Float32Array(n),preClass=new Uint8Array(n);
 for(let i=0;i<n;i++){
  let surface=base[i],id=0;
  if(state.forest){surface+=forest?.[i]||0;if(classes[i]===2)id=2}
  if(state.rivers&&classes[i]===1){surface=base[i]+(water?.[i]||0);id=1}
  if(state.grass&&classes[i]===5)id=5;
  if(state.snow&&classes[i]===3)id=3;
  if(state.houses&&houses?.[i]>0){surface=Math.max(surface,houses[i]);id=6}
  const weight=state.houses&&routeGap?.[i]?0:Math.max(0,Math.min(1,(.85-distance[i])/.13));
  z[i]=surface+weight*(Math.max(base[i],surface)-surface+.8);preClass[i]=id;
 }
 return {z,preClass};
}
export async function initFeatureControls({THREE,geo,mesh,scene,meta,onChange=()=>{}}){
 const spec=meta.preview_layers;if(!spec)throw Error('请先用新版配置重新构建模型');
 const read=async(url,Type)=>{if(!url)return null;const r=await fetch(url);if(!r.ok)throw Error(`图层加载失败 ${url}`);return new Type(await r.arrayBuffer())};
 const [base,classes,distance,forest,water,houses,faceRoute,routeGap,faceGap]=await Promise.all([read(spec.base,Float32Array),read(spec.classes,Uint8Array),read(spec.distance,Float32Array),read(spec.forest,Float32Array),read(spec.rivers,Float32Array),read(spec.houses,Float32Array),read(spec.face_route,Uint8Array),read(spec.route_gap,Uint8Array),read(spec.face_gap,Uint8Array)]);
 const layers={base,classes,distance,forest,water,houses,routeGap},state={...spec.available};
 const [nx,ny]=spec.grid,positions=geo.getAttribute('position').array,indices=geo.index.array;
 const samples=new Uint32Array(spec.top_faces);
 for(let i=0;i<samples.length;i++){
  const a=indices[i*3]*3,b=indices[i*3+1]*3,c=indices[i*3+2]*3;
  const x=(positions[a]+positions[b]+positions[c])/3,y=(positions[a+1]+positions[b+1]+positions[c+1])/3;
  samples[i]=Math.min(ny-1,Math.max(0,Math.round(y/meta.size[1]*(ny-1))))*nx+Math.min(nx-1,Math.max(0,Math.round(x/meta.size[0]*(nx-1))));
 }
 const pinGroup=new THREE.Group();scene.add(pinGroup);
 if(state.houses){const template=await loadPinHouse(THREE,meta.houses.model_glb);template.traverse(o=>{if(o.isMesh&&o.material.name==='accent')o.material.color.set(meta.configuration.effective.houses.pin_color)});for(const point of meta.houses.placed_points){const pin=template.clone(true);pin.scale.setScalar(meta.houses.scale);pin.position.fromArray(point.scene_origin_mm);pin.userData.photoIndex=point.photo_index;pinGroup.add(pin)}}

 const scaleGroup=new THREE.Group();scene.add(scaleGroup);
 if(state.elevation_scale){const [v,f]=await Promise.all([read(meta.elevation_scale.preview_vertices,Float32Array),read(meta.elevation_scale.preview_faces,Uint32Array)]);const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(v,3));g.setIndex(new THREE.BufferAttribute(f,1));g.computeVertexNormals();scaleGroup.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:meta.configuration.effective.elevation_scale.color,roughness:.85})));const note=document.createElement('p');note.style.cssText='font-size:11px;color:#acb9b1';note.textContent='海拔刻度位于'+({south:'南',north:'北',east:'东',west:'西'}[meta.elevation_scale.side])+'侧；'+(meta.elevation_scale.source==='route_start_end'?'按轨迹记录的起终点海拔等分；S=起点，E=终点。':'按 DEM 最低/最高海拔等分。')+(meta.elevation_scale.ticks.some(t=>t.relocated)?'* 表示标记因侧壁空间不足下移。':'全部刻度按真实海拔 Z 原位显示。');document.querySelector('#feature-switches').after(note)}
 const roadGroup=new THREE.Group();scene.add(roadGroup);
 for(const style of Object.values(meta.roads?.groups||{})){
  const vertices=await read(style.vertices,Float32Array),g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(vertices,3));
  const road=new THREE.Mesh(g,new THREE.MeshBasicMaterial({color:style.color,side:THREE.DoubleSide}));road.userData={style,original:vertices.slice()};roadGroup.add(road);
 }
 const roadNote=document.createElement('p');roadNote.id='road-status';roadNote.style.cssText='display:block;font-size:12px;color:#c9c7b8';
 const source=meta.sources?.roads;
 roadNote.textContent=meta.roads?.count?(source?.source_type==='local'?`本地文件 ${source.filename}`:`OSM · ${source?.endpoint?new URL(source.endpoint).hostname:'缓存'}`):(source?.available===false?'道路获取失败，可导入本地文件。':'该区域无道路，可导入本地文件。');
 document.querySelector('#feature-switches').after(roadNote);
 if(meta.job_id){
  const input=document.createElement('input');input.type='file';input.accept='.osm,.xml,.json,.geojson';input.hidden=true;
  const button=document.createElement('button');button.id='import-roads';button.textContent='导入道路文件';button.onclick=()=>input.click();
  input.onchange=async()=>{const file=input.files[0];if(!file)return;if(file.size>50000000){roadNote.textContent='道路文件最大 50 MB';return}button.disabled=true;roadNote.textContent='正在导入道路…';try{const response=await fetch(`/api/jobs/${meta.job_id}/roads?filename=${encodeURIComponent(file.name)}`,{method:'POST',body:file});const result=await response.json();if(!response.ok)throw Error(result.error);window.location.reload()}catch(error){roadNote.textContent=error.message;button.disabled=false}};
  roadNote.append(document.createTextNode(' '),button,input);
 }
 let lastRoadUnits=null;
 function updateRoadWidths(camera,renderer){
  if(!roadGroup.visible)return;
  const height=renderer.domElement.clientHeight||renderer.domElement.height||1;
  const center=new THREE.Vector3(meta.size[0]/2,meta.size[1]/2,0);center.applyMatrix4(scene.matrixWorld);
  const distance=camera.position.distanceTo(center);
  const units=camera.isOrthographicCamera?(camera.top-camera.bottom)/camera.zoom/height:2*distance*Math.tan(camera.fov*Math.PI/360)/(camera.zoom||1)/height;
  if(lastRoadUnits!==null&&Math.abs(units/lastRoadUnits-1)<=.05)return;lastRoadUnits=units;
  for(const road of roadGroup.children){const {style,original}=road.userData;if(!style.width_mm)continue;
   const width=Math.min(style.max_mm||style.width_mm*7,Math.max(style.width_mm,(style.min_px||1.5)*units));
   const ratio=width/style.width_mm;
   const p=road.geometry.attributes.position;
   // Each six-vertex segment stores two opposite edge pairs at its endpoints.
   for(let i=0;i+5<p.count;i+=6){
    const ax=(original[i*3]+original[(i+5)*3])/2,ay=(original[i*3+1]+original[(i+5)*3+1])/2;
    const bx=(original[(i+1)*3]+original[(i+2)*3])/2,by=(original[(i+1)*3+1]+original[(i+2)*3+1])/2;
    for(let j=0;j<6;j++){const a=[0,3,5].includes(j),cx=a?ax:bx,cy=a?ay:by,k=(i+j)*3;
     const x=Math.max(0,Math.min(meta.size[0],cx+(original[k]-cx)*ratio)),y=Math.max(0,Math.min(meta.size[1],cy+(original[k+1]-cy)*ratio));p.setXYZ(i+j,x,y,surfaceZ(x,y)+(meta.roads.lift_mm||.07));}
   }p.needsUpdate=true;road.geometry.computeBoundingSphere();
  }
 }
 const colors=meta.palette.map(x=>new THREE.Color(x.hex));
 const names={roads:`道路 (${meta.roads?.count||0})`,rivers:'河流/湖泊',forest:'林区',grass:'草地',snow:'冰雪',houses:`房屋 (${meta.houses?.placed_points?.length||0})`,elevation_scale:'海拔刻度'};
 const keysById={1:'rivers',2:'forest',3:'snow',5:'grass',6:'houses',7:'houses',8:'elevation_scale'};
 function legend(){
  const box=document.querySelector('#legend');box.replaceChildren();
  for(const item of meta.palette){if(item.id!==0&&item.id!==4&&!state[keysById[item.id]])continue;
   const span=document.createElement('span');span.className='legend-item';const dot=document.createElement('span');dot.className='swatch';dot.style.background=item.hex;span.append(dot,document.createTextNode(item.name.split(' / ')[1]));box.append(span)}
  if(state.roads)for(const style of Object.values(meta.roads.groups)){const span=document.createElement('span');span.className='legend-item';const dot=document.createElement('span');dot.className='swatch';dot.style.background=style.color;span.append(dot,document.createTextNode(style.label));box.append(span)}
  if(state.photos){const span=document.createElement('span');span.className='legend-item';const dot=document.createElement('span');dot.className='swatch';dot.style.background='#ffd45e';span.append(dot,document.createTextNode('照片点'+(meta.photos?.hike_date?' · '+meta.photos.hike_date:'')));box.append(span)}
 }
 function surfaceZ(x,y){
  const ix=Math.max(0,Math.min(nx-1,x/meta.size[0]*(nx-1))),iy=Math.max(0,Math.min(ny-1,y/meta.size[1]*(ny-1)));
  const i=Math.min(Math.floor(ix),nx-2),j=Math.min(Math.floor(iy),ny-2),fx=ix-i,fy=iy-j;
  const a=positions[(j*nx+i)*3+2],b=positions[(j*nx+i+1)*3+2],c=positions[((j+1)*nx+i)*3+2],d=positions[((j+1)*nx+i+1)*3+2];
  return fx>=fy?(1-fx)*a+(fx-fy)*b+fy*d:(1-fy)*a+fx*d+(fy-fx)*c;
 }
 function refresh(){
  const {z,preClass}=composePreview(layers,state);
  for(let i=0;i<z.length;i++)positions[i*3+2]=z[i];geo.attributes.position.needsUpdate=true;geo.computeVertexNormals();
  const next=geo.toNonIndexed(),rgb=new Float32Array(indices.length*3),counts={};
  for(let i=0;i<indices.length/3;i++){
   const id=i<spec.top_faces?(faceRoute[i]&&!(state.houses&&faceGap?.[i])?4:preClass[samples[i]]):0;
   const color=colors[id];counts[id]=(counts[id]||0)+1;
   for(let j=0;j<3;j++){const k=i*9+j*3;rgb[k]=color.r;rgb[k+1]=color.g;rgb[k+2]=color.b}
  }
  next.setAttribute('color',new THREE.BufferAttribute(rgb,3));next.computeBoundingBox();next.computeBoundingSphere();
  mesh.geometry.dispose();mesh.geometry=next;
  for(const pin of pinGroup.children)pin.position.z=surfaceZ(pin.position.x,pin.position.y)-meta.houses.sink_mm;
  roadGroup.visible=!!state.roads;
  for(const road of roadGroup.children){const attr=road.geometry.attributes.position;for(let i=0;i<attr.count;i++)attr.setZ(i,surfaceZ(attr.getX(i),attr.getY(i))+(meta.roads.lift_mm||.07));attr.needsUpdate=true;road.geometry.computeBoundingSphere()}
  pinGroup.visible=state.houses;scaleGroup.visible=state.elevation_scale;
  legend();window.featureStatus={enabled:{...state},available:{...spec.available},face_counts:counts,preview_only:true};onChange();
 }
 for(const [key,name] of Object.entries(names)){
  const button=document.createElement('button');button.textContent=spec.available[key]?name:`${name}（未构建）`;button.dataset.feature=key;button.disabled=!spec.available[key];button.setAttribute('aria-pressed',String(state[key]));button.classList.toggle('active',state[key]);
  button.addEventListener('click',()=>{state[key]=!state[key];button.setAttribute('aria-pressed',String(state[key]));button.classList.toggle('active',state[key]);refresh()});document.querySelector('#feature-switches').append(button);
 }
 window.addEventListener('photo-layer-visibility',e=>{state.photos=e.detail;legend();if(window.featureStatus)window.featureStatus.enabled.photos=e.detail});
 refresh();
 return {updateRoadWidths,surfaceAt:surfaceZ};
}
