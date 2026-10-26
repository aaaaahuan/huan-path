"""Persistent isolated tasks, with the same entry point for HTTP and CLI testing."""
from pathlib import Path
import json,sys,uuid,time,shutil,subprocess,os,hashlib,logging
import numpy as np
import rasterio
from .state import Progress,STAGES,write_json
from .tracks import parse_track,canonical
from .datasets import prepare_dem
ROOT=Path(__file__).resolve().parents[1]
JOBS=Path(os.environ.get('HUAN_PATH_JOBS_DIR') or ROOT/'jobs').expanduser().resolve()
JOBS.mkdir(parents=True,exist_ok=True)

def create_job(source=None,filename=None,content=None):
 name=filename or Path(source).name;suffix=Path(name).suffix.lower()
 if suffix not in ('.kmz','.kml'):raise ValueError('只接受 .kml / .kmz 文件')
 ident=time.strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:10];job=JOBS/ident;job.mkdir();(job/'data').mkdir()
 if content is not None:(job/('input'+suffix)).write_bytes(content)
 else:shutil.copyfile(source,job/('input'+suffix))
 track_file=None
 # 归档失败不能阻断地形任务；仅保留文件名，避免上传名称逃逸目录。
 if os.environ.get('HUAN_PATH_TRACKS_DIR'):
  try:
   tracks=Path(os.environ['HUAN_PATH_TRACKS_DIR']);tracks.mkdir(parents=True,exist_ok=True)
   target=tracks/Path(name).name
   original=job/('input'+suffix)
   if target.exists() and hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(original.read_bytes()).digest():
    target=tracks/f'{Path(name).stem}-{ident}{Path(name).suffix}'
   if not target.exists():shutil.copyfile(original,target)
   track_file=target.name
  except Exception:logging.exception('轨迹原文件归档失败，继续地形任务')
 write_json(job/'status.json',{'id':ident,'filename':Path(name).name,'input_file':'input'+suffix,'status':'queued','started_at':time.time(),'stages':[{'key':k,'name':n,'status':'pending','elapsed_seconds':None,'detail':''} for k,n in STAGES],'preview_url':f'/jobs/{ident}/web/','error':None,**({'track_file':track_file} if track_file else {})})
 return job

def run_job(job):
 job=Path(job);progress=Progress(job)
 if progress.state['status'] in ('completed','failed'):
  progress.state.update(started_at=time.time(),error=None,total_seconds=None,finished_at=None)
  progress.state['stages']=[{'key':k,'name':n,'status':'pending','elapsed_seconds':None,'detail':''} for k,n in STAGES]
 progress.state['worker_pid']=os.getpid();write_json(progress.path,progress.state)
 try:
  progress.stage('parse','解析 KML/KMZ、起终点、日期、轨迹与照片附件索引')
  state=json.loads((job/'status.json').read_text());info,coords,raw=parse_track(job/state['input_file'])
  if len(info['photo_points'])>500:raise ValueError('本地原型每任务最多 500 个照片点')
  previous=json.loads((job/'spec.json').read_text()) if (job/'spec.json').exists() else None
  imported=bool(previous and previous.get('preserve_imported_assets'))
  if imported:info=previous['route']
  (job/'data/source.kml').write_bytes(raw);canonical(coords,job/'data/route.kml')
  info['input_sha256']=__import__('hashlib').sha256((job/state['input_file']).read_bytes()).hexdigest()
  spec={'job_id':job.name,'data_dir':str(job/'data'),'input_file':state['input_file'],'route':info,'warnings':list(info['warnings']),'house_radius_m':75,'model':{'size_mm':200,'padding_m':1100,'base_mm':4,'vertical_exaggeration':None}}
  if imported:spec=previous
  spec.update(job_id=job.name,data_dir=str(job/'data'),input_file=state['input_file'])
  config_file=job/'config.json'
  config=json.loads(config_file.read_text()) if config_file.exists() else json.loads((ROOT/'config/features.json').read_text())
  config.pop('network',None)  # Network policy is global; never embed credentials in work metadata.
  config['houses']['list_file']=str(job/'data/photo_houses.json')
  defaults=json.loads((ROOT/'config/features.json').read_text())
  # 重试必须从当前任务重建路径，不能沿用迁移前的绝对 jobs 路径。
  for k in ('model_stl','model_glb'):
   local=job/'data/house_designs'/Path(config['houses'][k]).name
   config['houses'][k]=str(local if local.is_file() else (ROOT/defaults['houses'][k]).resolve())
  # Without photo points there is no need to advertise an empty photo layer.
  config['photos']['enabled']=config['photos']['enabled'] if imported else bool(info['photo_points'])
  write_json(config_file,config);write_json(job/'spec.json',spec)
  progress.detail(f"{info['name']} · {len(coords)} 点 · {len(info['photo_points'])} 照片点 · EPSG:{info['epsg']}")
  progress.stage('dem','按轨迹边界选择 Copernicus 瓦片，下载或复用真实缓存并裁剪')
  if not imported:prepare_dem(job,info)
  else:progress.detail('复用本作品保存的原始 DEM，保持既有模型比例和几何')
  if info['missing_altitude']:
   with rasterio.open(job/'data/dem.tif') as ds:coords[:,2]=[x[0] for x in ds.sample(coords[:,:2])]
   canonical(coords,job/'data/route.kml');spec['warnings'].append('轨迹缺少部分高程，本任务统一用 DEM 采样代替高程；刻度来源为 DEM 回填的首尾值');info['altitude_source']='DEM fallback'
  else:info['altitude_source']='recorded track'
  write_json(job/'spec.json',spec)
  with (job/'build.log').open('w') as log:
   # Inherit HUAN_PATH_JOBS_DIR; all build paths below belong to this job.
   result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'build_model.py'),str(job/'data/route.kml'),'--job-spec',str(job/'spec.json'),'--config',str(config_file),'--output-dir',str(job)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
  if result.returncode:
   lines=(job/'build.log').read_text(errors='replace').splitlines();raise RuntimeError('构建失败：'+'\n'.join(lines[-8:]))
  progress=Progress(job);progress.stage('preview','校验通过，封装独立网页、照片与下载链接')
  package_preview(job)
  Progress(job).finish()
 except Exception as ex:
  Progress(job).finish(str(ex));return False
 return True

def package_preview(job):
 spec=json.loads((job/'spec.json').read_text());web=job/'web'
 for name in ['index.html','features.js','places.js','photos.js','photos.css','pin-houses.js','product-info.js']:
  shutil.copyfile(ROOT/'web'/name,web/name)
 if (web/'vendor').exists():shutil.rmtree(web/'vendor')
 shutil.copytree(ROOT/'web/vendor',web/'vendor')
 metadata=json.loads((job/'models/validation.json').read_text())
 metadata.update(job_id=job.name,route_info=spec['route'],warnings=spec['warnings'],house_detection=spec.get('house_detection','no_photos'))
 metadata['photos']['enabled']=bool(metadata['photos']['total']) and metadata['configuration']['effective']['photos']['enabled']
 metadata['preview_layers']['available']['photos']=metadata['photos']['enabled']
 metadata['downloads']={'stl':'../models/terrain.stl','3mf':'../models/terrain.3mf'}
 for old,new in [('yubeng_ninong_print.stl','terrain.stl'),('yubeng_ninong_color.3mf','terrain.3mf')]:
  if (job/'models'/old).exists():(job/'models'/old).replace(job/'models'/new)
 write_json(web/'metadata.json',metadata);write_json(job/'models/validation.json',metadata)

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('track',nargs='?');parser.add_argument('--job');a=parser.parse_args()
 job=Path(a.job).resolve() if a.job else create_job(source=a.track)
 print(job,flush=True);ok=run_job(job);print((job/'status.json').read_text());sys.exit(0 if ok else 1)
