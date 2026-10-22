"""Real HTTP upload -> poll stages -> download/inspect two printable task models.
Run while server.py is running; no browser required. Source files are read-only.
"""
import os
import argparse,hashlib,json,time,urllib.request,urllib.error,concurrent.futures
from pathlib import Path
from urllib.parse import urlparse
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8766');parser.add_argument('--timeout',type=int,default=1800);args=parser.parse_args()
assert urlparse(args.url).port != 8765, '拒绝对真实 8765 作品库运行测试'
URL=args.url;ROOT=Path(__file__).resolve().parents[1]
env = os.environ.get('HUAN_PATH_JOBS_DIR')
assert env and not Path(env).resolve().is_relative_to((ROOT/'jobs').resolve()), '请使用临时 HUAN_PATH_JOBS_DIR，禁止向真实作品库上传测试作品'
jobs_root = Path(env).resolve()
def request(path,data=None,method=None):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));req=urllib.request.Request(URL+path,data=data,headers={'Content-Type':'application/octet-stream'} if data is not None else {},method=method)
 with opener.open(req,timeout=60) as r:return r.read(),r.status

def test(path):
 raw=path.read_bytes();before=hashlib.sha256(raw).hexdigest();from urllib.parse import quote
 body,code=request('/api/jobs?filename='+quote(path.name),raw,'POST');assert code==202;state=json.loads(body);ident=state['id'];deadline=time.monotonic()+args.timeout
 while time.monotonic()<deadline:
  body,_=request('/api/jobs/'+ident);state=json.loads(body)
  if state['status'] in ('failed','completed'):break
  time.sleep(1)
 assert state['status']=='completed',state
 prefix='/jobs/'+ident
 meta=json.loads(request(prefix+'/web/metadata.json')[0]);assert meta['route_info']['name'] and meta['crs']['epsg']==meta['route_info']['epsg'];assert meta['watertight'] and meta['connected_components']==1 and meta['export_checks']['flat_bottom_z_mm']==0 and meta['export_checks']['manifold_status']=='Error.NoError'
 assert meta['photos']['total']==(28 if path.suffix=='.kmz' else 0)
 # Every generated local import and data entry point is served, with generic route UI.
 html=request(prefix+'/web/')[0].decode();assert '<footer>' not in html and '数据来源' in html and '<summary>' in html
 assert 'product-info.js' in html
 for file in ('product-info.js','features.js','photos.js','pin-houses.js','vendor/three.module.js','vertices.bin','faces.bin'):
  assert request(prefix+'/web/'+file)[1]==200
 stl=request(prefix+'/models/terrain.stl')[0];three=request(prefix+'/models/terrain.3mf')[0];assert len(stl)>100 and three[:2]==b'PK'
 if meta['photos']['total']:
  points=json.loads(request(prefix+'/web/photos/points.json')[0])['points'];assert len(points)==28;assert request(prefix+'/web/'+points[0]['image'].removeprefix('./'))[1]==200
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before
 return {'job_id':ident,'filename':path.name,'status':state['status'],'total_seconds':state['total_seconds'],'stages':[{k:s[k] for k in ('key','name','status','elapsed_seconds','detail')} for s in state['stages']],'source_sha256':before,'photo_count':meta['photos']['total'],'house_detection':meta['house_detection'],'houses_placed':len(meta['houses']['placed_points']),'epsg':meta['crs']['epsg'],'vertices':meta['vertices'],'triangles':meta['triangles'],'dimensions_mm':meta['dimensions_mm'],'volume_cm3':meta['volume_cm3'],'export_checks':meta['export_checks'],'warnings':meta['warnings'],'preview_url':URL+prefix+'/web/'}
paths=[Path('/Users/huan/Desktop/paths/2026-01-27-yubeng.kmz'),Path('/Users/huan/Desktop/paths/2026-09-17-yubeng.kml')]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(test,paths))
(ROOT/'work/upload-e2e-results.json').write_text(json.dumps({'url':URL,'scope':'real HTTP upload, polling, task generation, downloads; no WebGL browser test','results':results},ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False,indent=2))
