"""Optional OSM roads: shared bbox cache, clipped model-space ribbon buffers."""
from pathlib import Path
import json
import numpy as np
from shapely.geometry import LineString, box
from .datasets import overpass
from .road_import import parse_roads,intersects
from .state import write_json

STYLES = {
 'major': {'label':'主干道路','color':'#ffc56a','width_mm':.55,'min_px':3.5,'max_mm':2.8},
 'secondary': {'label':'次干道路','color':'#fff0c2','width_mm':.40,'min_px':2.5,'max_mm':2.0},
 'local': {'label':'支路','color':'#f4ddba','width_mm':.28,'min_px':2,'max_mm':1.6},
 'trail': {'label':'小路','color':'#e9c18f','width_mm':.16,'min_px':1.5,'max_mm':1.2},
}
def classify(highway):
 if highway.removesuffix('_link') in ('motorway','trunk','primary'):return 'major'
 if highway.removesuffix('_link') in ('secondary','tertiary'):return 'secondary'
 if highway in ('residential','unclassified','service','living_street'):return 'local'
 if highway in ('track','path','footway','bridleway','steps','cycleway'):return 'trail'
 return None

def prepare_roads(data,bounds,warnings):
 data=Path(data)
 warnings[:]=[w for w in warnings if not w.startswith('道路获取失败')]
 try:
  local=data/'roads_import.json'
  if local.exists():
   raw=json.loads(local.read_text());source=json.loads((data/'roads_import_source.json').read_text())
  else:raw,source=overpass(bounds,highway=True)
  source['available']=True
 except Exception as ex:
  raw={'elements':[]};source={'available':False,'error':str(ex),'previous_errors':getattr(ex,'errors',[]),'proxy':getattr(ex,'proxy',{})}
  warnings.append('道路获取失败，本次无道路图层：'+str(ex))
 source.update(license='ODbL 1.0',attribution='© OpenStreetMap contributors',license_url='https://www.openstreetmap.org/copyright',bounds_wgs84=list(bounds))
 write_json(data/'osm_roads_raw.json',raw);write_json(data/'osm_roads_source.json',source)
 return raw

def build_roads(raw,tf,lo,hi,scale,web):
 """Clip in projected metres; densify every .12 model mm, including ribbon edges."""
 groups={k:[] for k in STYLES};counts={k:0 for k in STYLES};clip=box(*lo,*hi)
 def lines(g):
  if g.geom_type=='LineString':return [g]
  return [p for child in getattr(g,'geoms',[]) for p in lines(child)]
 for element in raw['elements']:
  kind=classify(element.get('tags',{}).get('highway',''))
  points=element.get('geometry',[])
  if element.get('type')!='way' or kind is None or len(points)<2:continue
  x,y=tf.transform([p['lon'] for p in points],[p['lat'] for p in points])
  parts=lines(LineString(zip(x,y)).intersection(clip))
  if not parts:continue
  counts[kind]+=1
  for line in parts:
   coords=(np.asarray(line.coords)-lo)*scale
   for a,b in zip(coords[:-1],coords[1:]):
    length=float(np.linalg.norm(b-a))
    if length<1e-8:continue
    normal=np.array([-(b-a)[1],(b-a)[0]])/length*STYLES[kind]['width_mm']/2
    n=max(1,int(np.ceil(length/.12)))
    for j in range(n):
     u=a+(b-a)*j/n;v=a+(b-a)*(j+1)/n
     groups[kind].extend([u-normal,v-normal,v+normal,u-normal,v+normal,u+normal])
 result={'count':sum(counts.values()),'counts':counts,'groups':{},'preview_only':True,'lift_mm':.07}
 web=Path(web);(web/'layers').mkdir(parents=True,exist_ok=True)
 for kind,points in groups.items():
  if not points:
   (web/'layers'/f'roads_{kind}.bin').unlink(missing_ok=True)
   continue
  xy=np.clip(np.array(points),0,(hi-lo)*scale)
  vertices=np.column_stack((xy,np.zeros(len(xy)))).astype('<f4')
  name=f'roads_{kind}.bin';vertices.tofile(web/'layers'/name)
  result['groups'][kind]={**STYLES[kind],'vertices':'./layers/'+name,'vertex_count':len(vertices)}
 return result


def import_roads(job,filename,content,bounds=None):
 raw=parse_roads(content)
 if bounds and not intersects(raw,bounds):raise ValueError('道路文件与作品区域不相交，请选择覆盖轨迹的文件')
 data=Path(job)/'data';name=Path(filename).name
 (data/('roads-upload'+Path(name).suffix.lower())).write_bytes(content)
 source={'source_type':'local','filename':name,'available':True}
 write_json(data/'roads_import.json',raw);write_json(data/'roads_import_source.json',source)
 return raw

def rebuild_roads(job):
 """Update preview buffers and metadata only; preserve printable artifacts."""
 from pyproj import Transformer
 job=Path(job);meta=json.loads((job/'web/metadata.json').read_text());spec=json.loads((job/'spec.json').read_text())
 bounds=json.loads((job/'data/osm_roads_source.json').read_text())['bounds_wgs84']
 tf=Transformer.from_crs(4326,spec['route']['epsg'],always_xy=True)
 rectangle=meta.get('features',{}).get('model_extent_projected_m')
 if rectangle is None:
  from .tracks import parse_track
  _,coords,_=parse_track(job/'data/route.kml')
  x,y=tf.transform(coords[:,0],coords[:,1]);xy=np.column_stack((x,y));lo=xy.min(axis=0)-spec['model']['padding_m'];hi=xy.max(axis=0)+spec['model']['padding_m']
 else:lo=np.array(rectangle[:2]);hi=np.array(rectangle[2:])
 raw=prepare_roads(job/'data',bounds,spec['warnings']);report=build_roads(raw,tf,lo,hi,spec['model']['size_mm']/max(hi-lo),job/'web')
 meta['roads']=report;meta['sources']['roads']=json.loads((job/'data/osm_roads_source.json').read_text());meta['preview_layers']['available']['roads']=report['count']>0;meta['warnings']=spec['warnings']
 for target in [job/'web/metadata.json',job/'models/validation.json']:write_json(target,meta)
 write_json(job/'spec.json',spec)
 return report
