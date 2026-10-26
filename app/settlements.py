"""Optional OSM settlements: place-name labels and land-use area overlay (preview only).

Follows app/roads.py: shared bbox Overpass cache with endpoint/OSM API fallback,
graceful failure with a warning, and never fabricated names or areas.
Nothing here touches printable STL/3MF geometry or materials.
"""
from pathlib import Path
import json,sys
import numpy as np
from shapely.geometry import LineString,Point,Polygon,box
from shapely.ops import polygonize,unary_union
from .datasets import overpass
from .state import write_json

PLACE_STYLES={
 'city':{'rank':1,'font_px':17},
 'town':{'rank':2,'font_px':15},
 'village':{'rank':3,'font_px':13},
 'hamlet':{'rank':4,'font_px':12},
 'locality':{'rank':5,'font_px':11},
}
# Burn order is ascending priority: residential wins where OSM areas overlap.
AREA_STYLES={
 3:{'key':'industrial','label':'工业区','color':'#9C93AE','landuse':('industrial',)},
 2:{'key':'commercial','label':'商业区','color':'#D4A35E','landuse':('commercial','retail')},
 1:{'key':'residential','label':'居民区','color':'#C98C7E','landuse':('residential',)},
}
MAX_LABELS=400
WARNING='聚落数据获取失败'

def place_name(tags):
 for key in ('name:zh','name:zh-Hans','name:zh-CN','name'):
  value=(tags.get(key) or '').strip()
  if value:return value
 return None

def area_code(tags):
 value=tags.get('landuse','')
 for code,style in AREA_STYLES.items():
  if value in style['landuse']:return code
 return None

def prepare_settlements(data,bounds,warnings):
 data=Path(data)
 warnings[:]=[w for w in warnings if not w.startswith(WARNING)]
 try:
  raw,source=overpass(bounds,settlement=True);source['available']=True
 except Exception as ex:
  raw={'elements':[]};source={'available':False,'error':str(ex),'previous_errors':getattr(ex,'errors',[]),'proxy':getattr(ex,'proxy',{})}
  warnings.append(WARNING+'，本次无地名/居民区图层：'+str(ex)[:300])
 source.update(license='ODbL 1.0',attribution='© OpenStreetMap contributors',license_url='https://www.openstreetmap.org/copyright',bounds_wgs84=list(bounds))
 write_json(data/'osm_settlements_raw.json',raw);write_json(data/'osm_settlements_source.json',source)
 return raw

def _ring(points,tf):
 if len(points)<2:return None
 x,y=tf.transform([p['lon'] for p in points],[p['lat'] for p in points])
 return LineString(zip(x,y))

def element_area(el,tf):
 """Closed way or multipolygon relation (outer minus inner) in projected metres."""
 if el.get('type')=='way':
  line=_ring(el.get('geometry',[]),tf)
  if line is None or len(line.coords)<4 or not line.is_closed:return None
  return Polygon(line.coords).buffer(0)
 if el.get('type')=='relation':
  outer=[];inner=[]
  for member in el.get('members',[]):
   if member.get('type')!='way':continue
   line=_ring(member.get('geometry',[]),tf)
   if line is None:continue
   (inner if member.get('role')=='inner' else outer).append(line)
  if not outer:return None
  shape=unary_union(list(polygonize(unary_union(outer))))
  if inner:shape=shape.difference(unary_union(list(polygonize(unary_union(inner)))))
  return None if shape.is_empty else shape.buffer(0)
 return None

def build_settlements(raw,tf,lo,hi,scale,web,grid):
 """Labels in model mm (z sampled in the browser) and a uint8 overlay on the preview grid."""
 from rasterio.features import rasterize
 from rasterio.transform import from_bounds
 lo=np.asarray(lo,dtype=float);hi=np.asarray(hi,dtype=float);size=(hi-lo)*scale;clip=box(*lo,*hi)
 nx,ny=map(int,grid);web=Path(web);(web/'layers').mkdir(parents=True,exist_ok=True)
 labels=[];seen=set();shapes={code:[] for code in AREA_STYLES};polygons={AREA_STYLES[c]['key']:0 for c in AREA_STYLES}
 for el in raw.get('elements',[]):
  tags=el.get('tags',{})
  if el.get('type')=='node' and tags.get('place') in PLACE_STYLES:
   name=place_name(tags)
   if not name or el.get('id') in seen:continue
   x,y=tf.transform(el['lon'],el['lat'])
   if not clip.covers(Point(x,y)):continue
   seen.add(el.get('id'));kind=tags['place']
   try:population=int(str(tags.get('population','')).replace(',',''))
   except ValueError:population=None
   labels.append({'name':name,'name_source':tags.get('name') if tags.get('name')!=name else None,'kind':kind,'rank':PLACE_STYLES[kind]['rank'],'x_mm':float((x-lo[0])*scale),'y_mm':float((y-lo[1])*scale),'population':population,'osm_id':el.get('id')})
   continue
  code=area_code(tags)
  if code is None or el.get('type') not in ('way','relation'):continue
  try:shape=element_area(el,tf)
  except Exception:shape=None
  if shape is None or shape.is_empty:continue
  shape=shape.intersection(clip)
  if shape.is_empty or shape.area<=0:continue
  from shapely.affinity import affine_transform
  shapes[code].append(affine_transform(shape,[scale,0,0,scale,-lo[0]*scale,-lo[1]*scale]));polygons[AREA_STYLES[code]['key']]+=1
 labels.sort(key=lambda r:(r['rank'],-(r['population'] or 0),r['name']))
 dropped=max(0,len(labels)-MAX_LABELS);labels=labels[:MAX_LABELS]
 counts={k:sum(r['kind']==k for r in labels) for k in PLACE_STYLES}
 places_path=web/'layers/places.json'
 if labels:write_json(places_path,{'labels':labels,'styles':PLACE_STYLES,'preview_only':True})
 else:places_path.unlink(missing_ok=True)
 # Same vertex-centred cells as build_model's grid; rows written south→north like classes.bin.
 dx=size[0]/(nx-1);dy=size[1]/(ny-1);transform=from_bounds(-dx/2,-dy/2,size[0]+dx/2,size[1]+dy/2,nx,ny)
 burn=[(g,code) for code in AREA_STYLES for g in shapes[code]]
 grid_codes=rasterize(burn,out_shape=(ny,nx),transform=transform,fill=0,dtype='uint8')[::-1].copy() if burn else np.zeros((ny,nx),dtype=np.uint8)
 cells={AREA_STYLES[c]['key']:int((grid_codes==c).sum()) for c in AREA_STYLES}
 area_path=web/'layers/settlements.bin'
 if grid_codes.any():grid_codes.astype('u1').tofile(area_path)
 else:area_path.unlink(missing_ok=True)
 styles={str(c):s for c,s in AREA_STYLES.items()}
 return {'preview_only':True,
  'places':{'count':len(labels),'counts':counts,'dropped_over_limit':dropped,'url':'./layers/places.json' if labels else None,'lift_mm':.6},
  'areas':{'polygons':polygons,'cells':cells,'grid':[nx,ny],'url':'./layers/settlements.bin' if grid_codes.any() else None,'styles':styles}}

def empty_report(web,grid):
 """No labels/areas: drop stale layer files so the viewer cannot show old data."""
 for name in ('places.json','settlements.bin'):(Path(web)/'layers'/name).unlink(missing_ok=True)
 return {'preview_only':True,'places':{'count':0,'counts':{k:0 for k in PLACE_STYLES},'dropped_over_limit':0,'url':None,'lift_mm':.6},
  'areas':{'polygons':{s['key']:0 for s in AREA_STYLES.values()},'cells':{s['key']:0 for s in AREA_STYLES.values()},'grid':list(grid),'url':None,'styles':{str(c):s for c,s in AREA_STYLES.items()}}}

def model_frame(job,meta,spec):
 from pyproj import Transformer
 tf=Transformer.from_crs(4326,spec['route']['epsg'],always_xy=True)
 rectangle=meta.get('features',{}).get('model_extent_projected_m')
 if rectangle is None:
  from .tracks import parse_track
  _,coords,_=parse_track(job/'data/route.kml')
  x,y=tf.transform(coords[:,0],coords[:,1]);xy=np.column_stack((x,y));lo=xy.min(axis=0)-spec['model']['padding_m'];hi=xy.max(axis=0)+spec['model']['padding_m']
 else:lo=np.array(rectangle[:2],dtype=float);hi=np.array(rectangle[2:],dtype=float)
 return tf,lo,hi

def wgs84_bounds(epsg,lo,hi):
 from pyproj import Transformer
 inverse=Transformer.from_crs(epsg,4326,always_xy=True)
 lon,lat=inverse.transform([lo[0],lo[0],hi[0],hi[0]],[lo[1],hi[1],lo[1],hi[1]])
 return [min(lon),min(lat),max(lon),max(lat)]

def apply_report(meta,report,source):
 meta['settlements']=report;meta.setdefault('sources',{})['settlements']=source
 layers=meta['preview_layers'];layers['settlements']=report['areas']['url'];layers['places']=report['places']['url']
 layers['available']['places']=report['places']['count']>0;layers['available']['settlements']=report['areas']['url'] is not None
 return meta

def rebuild_settlements(job):
 """Refresh preview-only settlement layers and metadata; printable artifacts are untouched."""
 job=Path(job);meta=json.loads((job/'web/metadata.json').read_text());spec=json.loads((job/'spec.json').read_text())
 tf,lo,hi=model_frame(job,meta,spec)
 raw=prepare_settlements(job/'data',wgs84_bounds(spec['route']['epsg'],lo,hi),spec['warnings'])
 report=build_settlements(raw,tf,lo,hi,spec['model']['size_mm']/max(hi-lo),job/'web',meta['preview_layers']['grid'])
 apply_report(meta,report,json.loads((job/'data/osm_settlements_source.json').read_text()));meta['warnings']=spec['warnings']
 for target in [job/'web/metadata.json',job/'models/validation.json']:
  if target.exists():write_json(target,meta)
 write_json(job/'spec.json',spec)
 return report

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Rebuild preview-only OSM place labels and settlement areas for existing works')
 parser.add_argument('jobs',nargs='+');parser.add_argument('--assets',action='store_true',help='also re-package the viewer (pipeline.package_preview: shared JS/HTML/vendor + metadata)')
 a=parser.parse_args();failed=0
 for item in a.jobs:
  job=Path(item).expanduser().resolve()
  try:
   report=rebuild_settlements(job)
   if a.assets:
    from .pipeline import package_preview
    package_preview(job)
   print(job.name,json.dumps({'places':report['places']['counts'],'areas':report['areas']['cells']},ensure_ascii=False),flush=True)
  except Exception as ex:
   failed+=1;print(job.name,'FAILED',ex,file=sys.stderr,flush=True)
 sys.exit(1 if failed else 0)
