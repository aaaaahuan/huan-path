"""Geographic tile selection, verified cache reuse and explicit missing-data provenance."""
from pathlib import Path
import json,math,hashlib,shutil,subprocess,time,tempfile
from datetime import datetime,timezone
import numpy as np
import rasterio
from rasterio.merge import merge
from .tracks import geo_tiles
from .state import write_json
import os,sys,urllib.request,re
from urllib.parse import urlsplit
from .road_import import way_geometry
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'cache';CACHE.mkdir(exist_ok=True)

def resolve_proxy(url,config=None):
 host=urlsplit(url).hostname
 if host in ('localhost','::1') or (host or '').startswith('127.'):return None,'loopback'
 if config is None:
  path=ROOT/'config/features.json'
  config=json.loads(path.read_text()) if path.exists() else {}
 value=config.get('network',config).get('proxy')
 if value:
  return (None,'config:off') if value=='off' else (value,'config')
 for key in ('HTTPS_PROXY','https_proxy','ALL_PROXY','all_proxy'):
  if os.environ.get(key):return os.environ[key],'env:'+key
 if sys.platform=='darwin':
  proxies=urllib.request.getproxies();value=proxies.get('https') or proxies.get('http') or proxies.get('all')
  if value:return value,'macOS system'
 return None,'direct'
def proxy_record(url):
 value,source=resolve_proxy(url)
 host=urlsplit(value).hostname if value else None
 return {'source':source,'host':host}

def seed_cache(source,target):
 if target.exists():return
 fd=tempfile.NamedTemporaryFile(dir=target.parent,suffix='.seed',delete=False);temp=Path(fd.name);fd.close()
 try:shutil.copyfile(source,temp);temp.replace(target)
 finally:
  if temp.exists():temp.unlink()

def fetch(url,target,params=None,timeout=50):
 target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 fd=tempfile.NamedTemporaryFile(dir=target.parent,prefix=target.name+'.',suffix='.part',delete=False);temp=Path(fd.name);fd.close()
 cmd=['curl','-fsSL','--connect-timeout','10','--max-time',str(timeout),'-A','HuanPathTerrain/2.0 local-model']
 proxy,_=resolve_proxy(url)
 # curl config stays on stdin so process listings never expose proxy credentials.
 escaped=(proxy or '').replace('\\','\\\\').replace('"','\\"').replace('\r','\\r').replace('\n','\\n')
 config='proxy = "'+escaped+'"\n'
 cmd+=['-K','-', '--noproxy','localhost,127.0.0.1,::1']
 if params:
  cmd+=['-G']
  for k,v in params.items():cmd+=['--data-urlencode',k+'='+v]
 cmd+=['-o',str(temp),url]
 try:
  try:p=subprocess.run(cmd,input=config,capture_output=True,text=True,timeout=timeout+.2)
  except subprocess.TimeoutExpired:raise RuntimeError('下载超时 '+url.split('?')[0]) from None
  if p.returncode:
   # Report only numeric status; curl diagnostics may echo proxy credentials.
   status=re.search(r'(?:error: |returned error: )(\d{3})',p.stderr or '')
   detail='HTTP '+status[1] if status else 'curl exit '+str(p.returncode)
   raise RuntimeError('下载失败 '+url.split('?')[0]+' '+detail)
  if temp.stat().st_size==0:raise RuntimeError('远程响应为空')
  temp.replace(target)
 finally:
  if temp.exists():temp.unlink()
 return target

def raster_mosaic(paths,target,bounds):
 with __import__('contextlib').ExitStack() as stack:
  datasets=[stack.enter_context(rasterio.open(p)) for p in paths]
  # Keep native source resolution; crop to upload region with a small resampling margin.
  w,s,e,n=bounds;pad=.002
  data,tr=merge(datasets,bounds=(w-pad,s-pad,e+pad,n+pad))
  profile=datasets[0].profile.copy();profile.update(driver='GTiff',height=data.shape[1],width=data.shape[2],transform=tr,compress='deflate')
  with rasterio.open(target,'w',**profile) as dst:dst.write(data)

def prepare_dem(job,info):
 data=Path(job)/'data';tiles=geo_tiles(info['bounds_wgs84'],1)
 if len(tiles)>16:raise ValueError('DEM 瓦片超过本地原型限制 16；请裁剪轨迹')
 paths=[];records=[]
 for lat,lon in tiles:
  name=f"Copernicus_DSM_COG_10_{'N' if lat>=0 else 'S'}{abs(lat):02d}_00_{'E' if lon>=0 else 'W'}{abs(lon):03d}_00_DEM"
  url=f'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif';cached=CACHE/(name+'.tif')
  existing=ROOT/'data/dem.tif'
  if not cached.exists() and existing.exists():
   with rasterio.open(existing) as src:
    if abs(src.bounds.left-lon)<.02 and abs(src.bounds.bottom-lat)<.02:seed_cache(existing,cached)
  hit=cached.exists()
  if not hit:fetch(url,cached,timeout=300)
  with rasterio.open(cached) as ds:
   if ds.crs.to_epsg()!=4326:raise ValueError('DEM 瓦片 CRS 不符')
  paths.append(cached);records.append({'tile':name,'url':url,'cache_hit':hit})
 raster_mosaic(paths,data/'dem.tif',info['bounds_wgs84'])
 record={'dataset':'Copernicus DEM GLO-30','license':'Copernicus DEM terms','attribution':'© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018. Provided under COPERNICUS by the European Union and ESA; all rights reserved.','license_url':'https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM','tiles':records,'bounds_wgs84':info['bounds_wgs84']};write_json(data/'dem_source.json',record)
 return record

SETTLEMENT_PLACES='city|town|village|hamlet|locality'
SETTLEMENT_LANDUSE='residential|commercial|retail|industrial'
# Overpass timing. Dense city areas (e.g. Hangzhou West Lake natural features, 2.3 MB) need ~50 s end to end,
# so the old 38 s client cap failed every mirror. Server [timeout:] is the query's own ceiling; the client
# waits that long plus transfer slack. A per-query budget caps the total instead of multiplying the long
# attempt by every endpoint, and a mirror that timed out earlier in this process is tried last next time.
OVERPASS_SERVER_TIMEOUT=90;OVERPASS_ATTEMPT=105;OVERPASS_BUDGET=240;OSM_API_RESERVE=60;OVERPASS_MIN_ATTEMPT=20
_slow_endpoints=set()  # endpoints that used a full attempt without answering; tried last next time
def endpoint_order(endpoints):
 return sorted(endpoints,key=lambda e:e in _slow_endpoints)  # stable: configured order otherwise
def overpass(bounds,building=False,highway=False,settlement=False):
 w,s,e,n=bounds;box=f'({s:.7f},{w:.7f},{n:.7f},{e:.7f})'
 tags=['way[waterway~"^(river|stream)$"]','nwr[natural=water]','nwr[landuse=forest]','nwr[natural~"^(wood|glacier)$"]']
 if building:tags=['nwr[building]']
 if highway:tags=['way["highway"]']
 if settlement:tags=[f'node[place~"^({SETTLEMENT_PLACES})$"]',f'way[landuse~"^({SETTLEMENT_LANDUSE})$"]',f'relation[landuse~"^({SETTLEMENT_LANDUSE})$"]']
 wide=highway or settlement
 body='('+''.join(t+box+';' for t in tags)+');out body geom;'
 query=f'[out:json][timeout:{OVERPASS_SERVER_TIMEOUT}];'+body
 # Cache identity is the data selection, not the server time limit; keep keys from the original [timeout:25] form.
 key=hashlib.sha256(('[out:json][timeout:25];'+body).encode()).hexdigest()[:24];cached=CACHE/('osm-'+key+'.json');errors=[]
 if cached.exists():
  try:
   doc=json.loads(cached.read_text())
   if 'elements' not in doc or 'remark' in doc:raise ValueError('缓存不完整')
   source=json.loads(cached.with_suffix('.source.json').read_text()) if cached.with_suffix('.source.json').exists() else {}
   if source.get('source_type')=='local':raise ValueError('忽略旧版本写入的本地导入缓存')
   return doc,{**source,'cache_hit':True,'query':query,'coverage_bounds_wgs84':bounds}
  except (ValueError,OSError):cached.unlink(missing_ok=True)
 reserve=OSM_API_RESERVE if wide else 0  # wide queries keep time for the OSM API fallback
 deadline=time.monotonic()+OVERPASS_BUDGET+reserve
 endpoints=['https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter'] if wide else ['https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']
 for endpoint in endpoint_order(endpoints):
  try:
   remaining=deadline-time.monotonic()-reserve
   if remaining<OVERPASS_MIN_ATTEMPT:
    errors.append({'endpoint':'budget','error':'Overpass 总预算耗尽'});break
   attempt=min(OVERPASS_ATTEMPT,remaining);started=time.monotonic()
   with tempfile.TemporaryDirectory(dir=CACHE) as tmp:
    downloaded=Path(tmp)/'response.json'
    try:fetch(endpoint,downloaded,{'data':query},timeout=attempt)
    except Exception:
     # Only a full-length timeout marks an endpoint slow; a budget-truncated try says nothing about it.
     if attempt==OVERPASS_ATTEMPT and time.monotonic()-started>=attempt-1:_slow_endpoints.add(endpoint)
     raise
    doc=json.loads(downloaded.read_text())
   if 'elements' not in doc or 'remark' in doc:raise ValueError('Overpass 返回不完整数据')
   _slow_endpoints.discard(endpoint)
   source={'cache_hit':False,'source_type':'overpass','proxy':proxy_record(endpoint),'endpoint':endpoint,'query':query,'coverage_bounds_wgs84':bounds,'timestamp':doc.get('osm3s',{}),'previous_errors':errors}
   cache_json(cached,doc);cache_json(cached.with_suffix('.source.json'),source)
   return doc,source
  except Exception as ex:
   errors.append({'endpoint':endpoint,'error':str(ex)})
 if wide and time.monotonic()<deadline:
  try:
   doc=osm_map(bounds,deadline,settlement_element if settlement else None);cache_json(cached,doc)
   source={'cache_hit':False,'source_type':'osm_api','map_tiles':doc.get('map_tiles'),'endpoint':'https://api.openstreetmap.org/api/0.6/map.json','proxy':proxy_record('https://api.openstreetmap.org'),'query':query,'coverage_bounds_wgs84':bounds,'previous_errors':errors}
   cache_json(cached.with_suffix('.source.json'),source)
   return doc,source
  except Exception as ex:errors.append({'endpoint':'osm_api','error':str(ex)})
 raise RoadFetchError(errors,proxy_record(endpoints[0]))

def prepare_features(job,spec,progress):
 data=Path(job)/'data';info=spec['route'];warnings=spec['warnings'];paths=[];wc_records=[]
 try:
  for lat,lon in geo_tiles(info['bounds_wgs84'],3):
   tile=f"{'N' if lat>=0 else 'S'}{abs(lat):02d}{'E' if lon>=0 else 'W'}{abs(lon):03d}"
   file=f'ESA_WorldCover_10m_2021_v200_{tile}_Map.tif';cached=CACHE/file;original=ROOT/f'data/worldcover_2021_{tile}.tif'
   if not cached.exists() and original.exists():seed_cache(original,cached)
   hit=cached.exists();url='https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/'+file
   if not hit:fetch(url,cached,timeout=180)
   paths.append(cached);wc_records.append({'tile':tile,'url':url,'cache_hit':hit})
  raster_mosaic(paths,data/'worldcover.tif',info['bounds_wgs84'])
  wc={'available':True,'tiles':wc_records}
 except Exception as ex:
  warnings.append('WorldCover 获取失败：'+str(ex));wc={'available':False,'error':str(ex),'tiles':wc_records}
  # Unknown category 0, not fabricated forest/grass/snow.
  with rasterio.open(data/'dem.tif') as src:
   profile=src.profile.copy();profile.update(dtype='uint8',nodata=0,count=1)
   with rasterio.open(data/'worldcover.tif','w',**profile) as dst:dst.write(np.zeros((1,src.height,src.width),dtype='u1'))
 wc.update(dataset='ESA WorldCover 10 m 2021 v200',license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',attribution='© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium');write_json(data/'worldcover_source.json',wc)
 try:osm,source=overpass(info['bounds_wgs84'])
 except Exception as ex:
  source={'error':str(ex),'available':False};osm={'elements':[]}
  raw=ROOT/'data/osm_features_raw.json'
  if raw.exists():
   # Reuse only the geographic intersection and disclose missing border coverage.
   import re
   query=(ROOT/'data/osm_query.overpassql').read_text();match=re.search(r'\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\)',query)
   if match:
    south,west,north,east=map(float,match.groups());w,s,e,n=info['bounds_wgs84']
    if max(w,west)<min(e,east) and max(s,south)<min(n,north):
     osm=json.loads(raw.read_text());source.update(available=True,cache_hit=True,partial_coverage=not(w>=west and s>=south and e<=east and n<=north),coverage_bounds_wgs84=[west,south,east,north],original_source=json.loads((ROOT/'data/osm_source.json').read_text()))
  warnings.append('OSM 在线获取失败；'+('使用已署名缓存，覆盖情况见来源记录' if source['available'] else '本任务未取得水系/林地补充数据')+'。'+str(ex))
 source.update(license='ODbL 1.0',attribution='© OpenStreetMap contributors',license_url='https://www.openstreetmap.org/copyright');write_json(data/'osm_features_raw.json',osm);write_json(data/'osm_source.json',source)
 if 'query' in source:(data/'osm_query.overpassql').write_text(source['query'])
 write_json(Path(job)/'spec.json',spec);progress.detail('数据已裁剪；'+ ('有获取限制，已记入警告' if warnings else '公开数据覆盖正常'))


def settlement_element(el):
 tags=el.get('tags',{})
 if el.get('type')=='node':return bool(re.fullmatch(SETTLEMENT_PLACES,tags.get('place','')))
 return el.get('type')=='way' and bool(re.fullmatch(SETTLEMENT_LANDUSE,tags.get('landuse','')))

def osm_map(bounds,deadline,keep=None):
 """Bounded recursive OSM map tiles, shared node table and way de-duplication.
 keep() selects output ways (default: highway) and tagged nodes (default: none)."""
 keep=keep or (lambda el:el.get('type')=='way' and bool(el.get('tags',{}).get('highway')))
 nodes={};ways={};tagged={};tiles=0
 def tile(b,depth=0):
  nonlocal tiles
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('道路总预算耗尽')
  w,s,e,n=b
  def split():
   if depth>=12:raise ValueError('OSM API 区域要素过密')
   if e-w>=n-s:
    m=(w+e)/2;tile([w,s,m,n],depth+1);tile([m,s,e,n],depth+1)
   else:
    m=(s+n)/2;tile([w,s,e,m],depth+1);tile([w,m,e,n],depth+1)
  if (e-w)*(n-s)>.25:return split()
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp)/'map.json'
   try:fetch('https://api.openstreetmap.org/api/0.6/map.json',target,{'bbox':','.join(map(str,b))},timeout=min(30,remaining));doc=json.loads(target.read_text())
   except Exception as ex:
    if re.search(r'\bHTTP 400\b',str(ex)):return split()
    raise
  tiles+=1
  for el in doc.get('elements',[]):
   if el['type']=='node':
    nodes[el['id']]={'lat':el['lat'],'lon':el['lon']}
    if el.get('tags') and keep(el):tagged[el['id']]={'type':'node','id':el['id'],'lat':el['lat'],'lon':el['lon'],'tags':el['tags']}
   elif el['type']=='way' and keep(el):ways[el['id']]=el
 tile(list(bounds))
 elements=list(tagged.values())
 for el in ways.values():
  geometry=way_geometry(el,nodes)
  if geometry:elements.append({'type':'way','id':el['id'],'tags':el['tags'],'geometry':geometry})
 return {'elements':elements,'map_tiles':tiles}


class RoadFetchError(RuntimeError):
 def __init__(self,errors,proxy):
  self.errors=errors;self.proxy=proxy
  super().__init__(json.dumps(errors,ensure_ascii=False))


def cache_json(path,doc):
 """Independent atomic writers, including simultaneous jobs of the same bbox."""
 path=Path(path)
 with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,suffix='.tmp',delete=False) as f:
  temp=Path(f.name);json.dump(doc,f,ensure_ascii=False)
 try:temp.replace(path)
 finally:temp.unlink(missing_ok=True)
