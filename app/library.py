"""Work summaries and explicit migration of the finished local model."""
from pathlib import Path
import json,time,shutil,hashlib
from .pipeline import ROOT,JOBS,create_job,package_preview
from .state import write_json

def read_optional_json(path):
 try:return json.loads(path.read_text())
 except (FileNotFoundError,json.JSONDecodeError):return {}

def summary(job):
 job=Path(job);s=json.loads((job/'status.json').read_text());result=dict(s)
 meta=job/'web/metadata.json';houses=job/'data/photo_houses.json'
 m=read_optional_json(meta)
 if m:
  info=m.get('route_info',{})
  result.update(name=s.get('name') or info.get('name') or s['filename'],date=info.get('date',''),photo_count=m.get('photos',{}).get('total',0),house_count=len(m.get('houses',{}).get('placed_points',[])))
 else:result.update(name=s.get('name') or s['filename'],date='',photo_count=0,house_count=0)
 result['uncertain_houses']=0
 h=read_optional_json(houses)
 if h:
  result['house_method']=h.get('method');result['uncertain_houses']=sum(p.get('has_house')=='uncertain' for p in h.get('points',[]))
 return result

def import_finished_work():
 # Idempotent: no extra copies if this migration is explicitly invoked again.
 for p in JOBS.glob('*/status.json'):
  if json.loads(p.read_text()).get('origin')=='imported_finished_model':return p.parent
 from .tracks import parse_track
 job=create_job(source=ROOT/'data/route.kml',filename='2026-09-17-yubeng.kml');data=job/'data';info,_,_=parse_track(ROOT/'data/route.kml');info['name']='雨崩 · 尼农线'
 m=json.loads((ROOT/'web/metadata.json').read_text());cfg=json.loads((ROOT/'config/features.json').read_text())
 for source,target in [('dem.tif','dem.tif'),('worldcover_2021_N27E096.tif','worldcover.tif'),('route.kml','route.kml'),('osm_features_raw.json','osm_features_raw.json'),('osm_source.json','osm_source.json'),('osm_query.overpassql','osm_query.overpassql'),('worldcover_source.json','worldcover_source.json'),('photo_houses.json','photo_houses.json')]:shutil.copyfile(ROOT/'data'/source,data/target)
 shutil.copytree(ROOT/'data/photos-2026-01-27',data/'photos');shutil.copytree(ROOT/'data/house_designs',data/'house_designs')
 for key in ('model_stl','model_glb'):cfg['houses'][key]=str(data/'house_designs'/Path(cfg['houses'][key]).name)
 cfg['houses']['list_file']=str(data/'photo_houses.json');write_json(job/'config.json',cfg)
 write_json(data/'dem_source.json',{'dataset':'Copernicus DEM GLO-30','source':m.get('source'),'license':'Copernicus DEM terms','attribution':'© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018. Provided under COPERNICUS by the European Union and ESA; all rights reserved.'})
 spec={'job_id':job.name,'data_dir':str(data),'input_file':'input.kml','route':info,'preserve_imported_assets':True,'warnings':['照片与房屋判断来自 2026-01-27，基础轨迹为 2026-09-17；沿用已确认的人工判断。'],'house_detection':'manual','house_radius_m':75,'model':{'size_mm':float(max(m['size'])),'padding_m':1100,'base_mm':m['base_mm'],'vertical_exaggeration':m['vertical_exaggeration']}}
 write_json(job/'spec.json',spec);shutil.copytree(ROOT/'web',job/'web');(job/'models').mkdir(exist_ok=True)
 for name in ('yubeng_ninong_print.stl','yubeng_ninong_color.3mf','validation.json'):shutil.copyfile(ROOT/'models'/name,job/'models'/name)
 package_preview(job)
 state=json.loads((job/'status.json').read_text());state.update(name=info['name'],origin='imported_finished_model',status='completed',error=None,finished_at=time.time(),total_seconds=None)
 for stage in state['stages']:stage.update(status='done',elapsed_seconds=None,detail='从已完成作品导入，保留原模型与人工标注')
 write_json(job/'status.json',state)
 for src,dst in [('models/yubeng_ninong_print.stl','models/terrain.stl'),('models/yubeng_ninong_color.3mf','models/terrain.3mf')]:
  assert hashlib.sha256((ROOT/src).read_bytes()).digest()==hashlib.sha256((job/dst).read_bytes()).digest()
 return job
