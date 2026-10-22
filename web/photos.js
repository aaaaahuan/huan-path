// UI-only photo overlay. No printed mesh or material data is modified.
export async function initPhotoLayer({THREE,scene,camera,renderer,controls,terrain,meta,surfaceAt=null}) {
 const response=await fetch(meta.photos?.data_url || './photos/points.json');
 if(!response.ok)throw Error(`照片数据加载失败 (${response.status})`);
 const {summary,points}=await response.json();
 const valid=points.filter(p=>p.in_model && p.model_position_mm.every(Number.isFinite));
 const layer=new THREE.Group();layer.name='Photo waypoints (preview only)';scene.add(layer);
 const sprites=[];const anchors=[];const raycaster=new THREE.Raycaster();const pointer=new THREE.Vector2();
 const tip=document.querySelector('#photo-tooltip');const dialog=document.querySelector('#photo-dialog');
 const list=document.querySelector('#photo-list');const toggle=document.querySelector('#photos-toggle');
 const listToggle=document.querySelector('#photo-list-toggle');let active=-1;let down=null;let wasRotating=false;
 const text=(id,value)=>{document.getElementById(id).textContent=value};
 text('photo-source',`照片：${summary.hike_date||'日期未知'} · ${summary.in_bounds}/${summary.total} 点在模型内${summary.same_hike_as_base_route?'':' · 与红色路线不是同一次徒步'}`);
 if(document.querySelector('#photo-date-disclaimer'))text('photo-date-disclaimer',summary.same_hike_as_base_route?'照片来自本次上传轨迹。':`照片来自 ${summary.hike_date}「${summary.hike_label}」，与主路线不是同一次徒步。`);
 text('photo-list-title',`${summary.hike_date||'日期未知'} · ${summary.total} 张照片`);
 listToggle.textContent=`照片列表 (${summary.total})`;
 const elevation=p=>p.dem_elevation_m===null?'范围外，未采样':`${p.dem_elevation_m.toFixed(1)} 米（DEM）`;
 function makeTexture(index){
  const canvas=document.createElement('canvas');canvas.width=96;canvas.height=96;const ctx=canvas.getContext('2d');
  ctx.beginPath();ctx.arc(48,48,39,0,Math.PI*2);ctx.fillStyle='#FFD45E';ctx.fill();ctx.lineWidth=7;ctx.strokeStyle='#152827';ctx.stroke();
  ctx.fillStyle='#142725';ctx.font='bold 38px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(index),48,50);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return texture;
 }
 for(const p of valid){
  const [x,y,z]=p.model_position_mm;
  const visibleZ=Math.max(z,surfaceAt?.(x,y)??p.rendered_surface_z_mm??z)+p.marker_lift_mm;
  const stemGeo=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x,y,z),new THREE.Vector3(x,y,visibleZ)]);
  layer.add(new THREE.Line(stemGeo,new THREE.LineBasicMaterial({color:0xffd45e})));
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:makeTexture(p.index),depthTest:true,depthWrite:false,transparent:true}));
  sprite.position.set(x,y,visibleZ);sprite.userData.photo=p;sprite.scale.set(3.6,3.6,1);layer.add(sprite);sprites.push(sprite);anchors.push({p,sprite,stemGeo});
 }
 function hideTip(){tip.hidden=true;renderer.domElement.style.cursor=''}
 function showPhoto(p){
  active=points.findIndex(q=>q.id===p.id);
  text('photo-title',`${p.label} · ${summary.hike_label||summary.hike_date||'徒步照片'}`);
  const img=document.querySelector('#photo-full');img.src=p.image;img.alt=`${p.label}，标注于 ${p.time_local}`;
  text('photo-time',`${p.time_local}（北京时间 / UTC+8）`);
  text('photo-elevation',elevation(p));
  text('photo-coordinates',`${p.longitude.toFixed(6)}° E，${p.latitude.toFixed(6)}° N`);
  text('photo-id',p.id);text('photo-boundary',p.in_model?'在当前模型范围内':'模型范围外（不显示 3D 标记）');
  text('photo-caption',p.note || '原始标注未填写名称和文字备注。');
  document.querySelector('#photo-prev').disabled=active===0;document.querySelector('#photo-next').disabled=active===points.length-1;
  if(!dialog.open){wasRotating=controls.autoRotate;controls.autoRotate=false;dialog.showModal()}
  hideTip();window.photoStatus.selected_id=p.id;
 }
 for(const p of points){
  const button=document.createElement('button');button.className='photo-card';button.type='button';button.setAttribute('aria-label',`查看${p.label}，${p.time_local}`);
  const img=document.createElement('img');img.src=p.thumbnail;img.alt='';img.loading='lazy';img.width=96;img.height=80;
  const title=document.createElement('span');title.textContent=`${p.label} · ${p.time_local.slice(11,16)}${p.in_model?'':' · 范围外'}`;
  button.append(img,title);button.addEventListener('click',()=>showPhoto(p));document.querySelector('#photo-cards').append(button);
 }
 toggle.disabled=false;toggle.setAttribute('aria-pressed','true');toggle.classList.add('active');
 toggle.addEventListener('click',()=>{layer.visible=!layer.visible;toggle.setAttribute('aria-pressed',String(layer.visible));toggle.classList.toggle('active',layer.visible);window.photoStatus.visible=layer.visible;window.dispatchEvent(new window.CustomEvent('photo-layer-visibility',{detail:layer.visible}));hideTip()});
 listToggle.disabled=false;listToggle.addEventListener('click',()=>{list.hidden=!list.hidden;listToggle.setAttribute('aria-expanded',String(!list.hidden))});
 document.querySelector('#photo-list-close').addEventListener('click',()=>{list.hidden=true;listToggle.setAttribute('aria-expanded','false');listToggle.focus()});
 document.querySelector('#photo-close').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>{controls.autoRotate=wasRotating;window.photoStatus.selected_id=null});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
 document.querySelector('#photo-prev').addEventListener('click',()=>{if(active>0)showPhoto(points[active-1])});
 document.querySelector('#photo-next').addEventListener('click',()=>{if(active<points.length-1)showPhoto(points[active+1])});
 dialog.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'&&active>0){e.preventDefault();showPhoto(points[active-1])}if(e.key==='ArrowRight'&&active<points.length-1){e.preventDefault();showPhoto(points[active+1])}});
 function hit(event){
  if(!layer.visible||dialog.open)return null;
  const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
  raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(sprites,false);if(!hits.length)return null;
  // Do not allow clicking a marker through an intervening mountain.
  const ground=raycaster.intersectObject(terrain,false)[0];
  return ground&&ground.distance<hits[0].distance-.5 ? null : hits[0].object.userData.photo;
 }
 renderer.domElement.addEventListener('pointermove',e=>{
  if(e.buttons){hideTip();return}const p=hit(e);if(!p){hideTip();return}
  tip.replaceChildren();const name=document.createElement('strong');name.textContent=p.label;const time=document.createElement('div');time.textContent=p.time_local;const alt=document.createElement('div');alt.textContent=`海拔 ${elevation(p)}`;
  tip.append(name,time,alt);tip.hidden=false;tip.style.left=`${Math.max(4,Math.min(e.clientX+14,innerWidth-245))}px`;tip.style.top=`${Math.max(4,Math.min(e.clientY+14,innerHeight-100))}px`;renderer.domElement.style.cursor='pointer';
 });
 renderer.domElement.addEventListener('pointerleave',hideTip);
 renderer.domElement.addEventListener('pointerdown',e=>{if(e.button!==0)return;down={x:e.clientX,y:e.clientY};hideTip()});
 renderer.domElement.addEventListener('pointerup',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)<5){const p=hit(e);if(p)showPhoto(p)}down=null});
 controls.addEventListener('change',hideTip);
 window.photoStatus={loaded:true,total:points.length,markers:sprites.length,out_of_bounds:summary.out_of_bounds,visible:true,selected_id:null,hike_date:summary.hike_date};
 return {refreshSurface(){
  for(const {p,sprite,stemGeo} of anchors){const [x,y,z]=p.model_position_mm;const top=Math.max(z,surfaceAt?.(x,y)??p.rendered_surface_z_mm??z)+p.marker_lift_mm;sprite.position.z=top;stemGeo.attributes.position.array[5]=top;stemGeo.attributes.position.needsUpdate=true;stemGeo.computeBoundingSphere()}
  hideTip();
 },update(){
  const h=renderer.domElement.clientHeight||innerHeight;
  for(const sprite of sprites){const size=camera.position.distanceTo(sprite.position)*2*Math.tan(camera.fov*Math.PI/360)/h*22;sprite.scale.set(size,size,1)}
 }};
}
