import os,shutil
import urllib.request,urllib.error,json,argparse,time,sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8766');args=parser.parse_args();opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
assert urlparse(args.url).port != 8765, '拒绝对真实 8765 作品库运行测试'
real_jobs=Path(__file__).resolve().parents[1]/'jobs'
env = os.environ.get('HUAN_PATH_JOBS_DIR')
assert env and not Path(env).resolve().is_relative_to(real_jobs.resolve()), '请通过 tests/run_http_suite.py 使用临时作品根'
jobs_root = Path(env).resolve()
def req(path,data=None,headers=None):
 r=urllib.request.Request(args.url+path,data=data,headers=headers or {})
 try:
  with opener.open(r,timeout=10) as response:return response.status,response.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
assert req('/api/health')[0]==200
assert req('/')[0]==200
assert req('/api/jobs',b'x',{'Origin':'https://example.com'})[0]==403
assert req('/api/jobs?filename=bad.txt',b'x')[0]==400
assert req('/app/../../config/features.json')[0]==404
assert req('/.env')[0]==404
job=None
try:
 # A malicious/invalid XML upload is isolated, returns immediately, and fails visibly.
 code,raw=req('/api/jobs?filename=invalid.kml',b'<!DOCTYPE foo><kml/>');assert code==202;job=json.loads(raw)['id']
 for _ in range(60):
  state=json.loads(req('/api/jobs/'+job)[1])
  if state['status']=='failed':break
  time.sleep(.1)
 assert state['status']=='failed' and 'DTD' in state['error'];assert req('/jobs/'+job+'/web/')[0]==404
 assert req('/api/jobs/'+job+'/retry',b'')[0]==202
 for _ in range(60):
  if json.loads(req('/api/jobs/'+job)[1])['status']=='failed':break
  time.sleep(.1)
 from app.state import write_json
 root=jobs_root/job
 write_json(root/'data/photo_houses.json',{'method':'osm_nearby','points':[{'photo_index':1,'longitude':100.,'latitude':30.,'has_house':'uncertain','reason':'test'}]})
 code,body=req('/api/jobs/'+job+'/houses',json.dumps({'points':[{'photo_index':1,'has_house':True,'reason':'reviewed','longitude':0}]}).encode(),{'Content-Type':'application/json'});assert code==200
 updated=json.loads(req('/api/jobs/'+job+'/houses')[1]);assert updated['points'][0]['has_house'] is True and updated['points'][0]['longitude']==100. and updated['method']=='manual'
finally:
 if job is not None:shutil.rmtree(jobs_root/job, ignore_errors=True)
print('HTTP validation passed: upload errors, async failure/retry, manual house editing, origin guard and path isolation')
