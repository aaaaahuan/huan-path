export function initProductInfo(meta){
 const $=s=>document.querySelector(s),info=meta.route_info||{};
 const panel=$('.panel'),panelContent=$('#panel-content'),panelToggle=$('#panel-toggle');
 if(panelToggle){
  const setCollapsed=collapsed=>{panel.classList.toggle('is-collapsed',collapsed);panelContent.hidden=collapsed;panelToggle.textContent=collapsed?'‹ 展开':'收起 ›';panelToggle.setAttribute('aria-expanded',String(!collapsed));panelToggle.title=collapsed?'展开配置面板':'收起配置面板'};
  try{setCollapsed(window.localStorage.getItem('trail:model-panel-collapsed')==='true')}catch{setCollapsed(false)}
  panelToggle.onclick=()=>{const collapsed=!panelContent.hidden;setCollapsed(collapsed);try{window.localStorage.setItem('trail:model-panel-collapsed',String(collapsed))}catch{}};
 }
 const embedded=new URLSearchParams(location.search).get('embedded')==='1'&&window.parent!==window;
 document.body.classList.toggle('workbench-embedded',embedded);
 function navigate(inspect=false){if(embedded)window.parent.postMessage({type:'workbench:select',jobId:meta.job_id,inspect},location.origin);else location.href='/?job='+meta.job_id+(inspect?'&inspect=1':'')}
 const upload=$('.new-upload');if(upload){upload.hidden=embedded;upload.href='/';}
 $('#route-title').textContent=info.name||'徒步地形模型';document.title=(info.name||'徒步地形模型')+' · TRAIL MEMORIES';
 $('#route-subtitle').textContent=[info.date,[info.start_name,info.end_name].filter(Boolean).join(' → ')].filter(Boolean).join('　');
 $('#route-distance').textContent=Number(info.recorded_distance_km??meta.kml_recorded_distance_km??meta.track_distance_km).toFixed(2);
 $('#exaggeration').textContent=meta.vertical_exaggeration.toFixed(2)+' ×';
 for(const [key,url] of Object.entries(meta.downloads||{})){const a=document.querySelector(`a[download][href$=".${key==='3mf'?'3mf':'stl'}"]`);if(a)a.href=url}
 const notes=$('#job-notes');const source={openai_vision:'视觉模型逐张判断',osm_nearby:'OSM 拍摄点附近建筑推断（非照片识别）',manual:'人工修正',no_photos:'无照片，未进行房屋判断'}[meta.house_detection]||'示例：原图视觉初判，可人工修改';
 notes.closest('details').querySelector('summary').textContent='生成说明 · '+source;
 notes.textContent='房屋来源：'+source+'\n'+(meta.house_detection==='osm_nearby'?'在拍摄点附近 75 m 内查找 OSM building；获取失败则 uncertain，不放置。\n':'')+(meta.warnings||[]).join('\n');
 if(meta.job_id){const link=document.createElement('a');link.href='/?job='+meta.job_id+'&inspect=1';link.textContent='查看阶段耗时与任务记录 ↗';link.onclick=event=>{event.preventDefault();navigate(true)};notes.append(document.createElement('br'),link)}
 if(!meta.job_id||!meta.photos?.total)return;
 const button=$('#edit-houses');button.hidden=false;const dialog=$('#houses-dialog');let doc;
 async function request(url,options){const r=await fetch(url,options),d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d}
 button.onclick=async()=>{try{doc=await request('/api/jobs/'+meta.job_id+'/houses');$('#house-rows').replaceChildren();for(const p of doc.points){const row=document.createElement('div');row.className='house-row';row.dataset.index=p.photo_index;const label=document.createElement('span');label.textContent=p.photo_index;const select=document.createElement('select');for(const [value,text] of [['true','有房屋'],['false','无房屋'],['uncertain','不确定']]){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option)}select.value=String(p.has_house);const reason=document.createElement('input');reason.value=p.reason;reason.maxLength=500;row.append(label,select,reason);$('#house-rows').append(row)}$('#house-edit-error').textContent='';dialog.showModal()}catch(e){notes.textContent+='\n'+e.message}};
 $('#house-cancel').onclick=()=>dialog.close();$('#house-save').onclick=async()=>{try{const points=[...$('#house-rows').children].map(row=>({photo_index:Number(row.dataset.index),has_house:row.querySelector('select').value==='uncertain'?'uncertain':row.querySelector('select').value==='true',reason:row.querySelector('input').value}));await request('/api/jobs/'+meta.job_id+'/houses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points})});await request('/api/jobs/'+meta.job_id+'/retry',{method:'POST'});navigate(false)}catch(e){$('#house-edit-error').textContent=e.message}};
}
