#!/usr/bin/env python3
"""Loopback-only application server. No filesystem-wide static file serving."""
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,unquote
from concurrent.futures import ThreadPoolExecutor
import json,mimetypes,os,re,time,threading,shutil,argparse
from app.pipeline import ROOT,JOBS,create_job,run_job
from app.state import write_json,STAGES
from app.library import summary
EXECUTOR=ThreadPoolExecutor(max_workers=2);LOCK=threading.Lock();ACTIVE=set();MAX_UPLOAD=150_000_000
ID=re.compile(r'^\d{8}-\d{6}-[a-f0-9]{10}$')
def launch(job):
 with LOCK:
  if job.name in ACTIVE:raise ValueError('该任务正在运行')
  ACTIVE.add(job.name)
 def work():
  try:run_job(job)
  finally:
   with LOCK:ACTIVE.discard(job.name)
 EXECUTOR.submit(work)

def retry(job):
 with LOCK:
  if job.name in ACTIVE:raise ValueError('任务尚在运行')
 old=json.loads((job/'status.json').read_text());attempts=job/'attempts';attempts.mkdir(exist_ok=True)
 write_json(attempts/f'{int(time.time()*1000)}.json',old)
 old.update(status='queued',error=None,started_at=time.time(),stages=[{'key':k,'name':n,'status':'pending','elapsed_seconds':None,'detail':''} for k,n in STAGES]);old.pop('finished_at',None);old.pop('total_seconds',None);write_json(job/'status.json',old);launch(job)

class Handler(BaseHTTPRequestHandler):
 server_version='HuanTerrain/2.0'
 def json(self,value,status=200):
  data=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
 def permitted(self):
  host=self.headers.get('Host','');allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
  if host not in allowed:self.json({'error':'仅允许本机 Host'},403);return False
  origin=self.headers.get('Origin')
  if origin and origin not in {'http://'+h for h in allowed}:self.json({'error':'不接受跨域请求'},403);return False
  return True
 def job(self,ident):
  if not ID.fullmatch(ident):raise ValueError('任务编号无效')
  path=JOBS/ident
  if not (path/'status.json').is_file():raise FileNotFoundError('任务不存在')
  return path
 def do_GET(self):
  if not self.permitted():return
  path=unquote(urlparse(self.path).path)
  if path.endswith('/favicon.ico'):
   self.send_response(204);self.end_headers();return
  try:
   if path in ('/web','/web/'):
    imported=next((summary(p.parent) for p in JOBS.glob('*/status.json') if json.loads(p.read_text()).get('origin')=='imported_finished_model'),None)
    self.send_response(303);self.send_header('Location','/?job='+imported['id'] if imported else '/');self.end_headers();return
   if path=='/api/health':return self.json({'service':'huan-terrain','version':2})
   if path=='/api/jobs':
    rows=[summary(p.parent) for p in sorted(JOBS.glob('*/status.json'),reverse=True)];return self.json(rows)
   parts=path.strip('/').split('/')
   if len(parts)>=3 and parts[:2]==['api','jobs']:
    job=self.job(parts[2])
    if len(parts)==3:return self.json(summary(job))
    if parts[3:] == ['houses']:return self.json(json.loads((job/'data/photo_houses.json').read_text()))
    raise FileNotFoundError()
   if path in ('/','/upload','/app/'):target=ROOT/'app/ui/index.html';base=ROOT/'app/ui'
   elif path.startswith('/app/'):
    base=ROOT/'app/ui';target=base/path[len('/app/'):]
   elif parts[0] in ('web','models'):
    base=ROOT/parts[0];target=base/('/'.join(parts[1:]) or 'index.html')
   elif len(parts)>=3 and parts[0]=='jobs' and parts[2] in ('web','models'):
    job=self.job(parts[1]);state=json.loads((job/'status.json').read_text())
    if state['status']!='completed':raise FileNotFoundError('任务未完成')
    base=job/parts[2];target=base/('/'.join(parts[3:]) or 'index.html')
   else:raise FileNotFoundError()
   target=target.resolve();base=base.resolve()
   if not target.is_relative_to(base) or target.suffix.lower() not in {'.html','.js','.css','.bin','.json','.glb','.jpg','.png','.stl','.3mf'}:raise FileNotFoundError()
   if not target.is_file():raise FileNotFoundError()
   self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream');self.send_header('Content-Length',str(target.stat().st_size));self.send_header('Cache-Control','no-cache');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
   with target.open('rb') as f:shutil.copyfileobj(f,self.wfile)
  except FileNotFoundError as e:self.json({'error':str(e) or '资源不存在'},404)
  except ValueError as e:self.json({'error':str(e)},400)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_POST(self):
  if not self.permitted():return
  try:
   parsed=urlparse(self.path);parts=parsed.path.strip('/').split('/')
   if parsed.path=='/api/jobs':
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=MAX_UPLOAD:return self.json({'error':'文件不能为空，最大 150 MB'},413)
    filename=parse_qs(parsed.query).get('filename',[''])[0]
    if Path(filename).suffix.lower() not in ('.kml','.kmz'):raise ValueError('只接受 KML / KMZ')
    # Read only bounded bytes; use a task-local temporary upload, not a supplied path.
    import tempfile
    with tempfile.NamedTemporaryFile(dir=JOBS,suffix=Path(filename).suffix.lower()) as temp:
     remaining=length;self.connection.settimeout(45)
     while remaining:
      block=self.rfile.read(min(1024*1024,remaining))
      if not block:raise ValueError('上传提前中断')
      temp.write(block);remaining-=len(block)
     temp.flush();job=create_job(source=temp.name,filename=filename)
    if parse_qs(parsed.query).get('defer')!=['1']:launch(job)
    return self.json(json.loads((job/'status.json').read_text()),202)
   if len(parts)==4 and parts[:2]==['api','jobs'] and parts[3]=='roads':
    from app.roads import import_roads,rebuild_roads
    job=self.job(parts[2])
    with LOCK:
     if job.name in ACTIVE:raise ValueError('请等待当前任务结束再导入')
     ACTIVE.add(job.name)
    try:
     length=int(self.headers.get('Content-Length','0'))
     if not 0<length<=50_000_000:return self.json({'error':'道路文件不能为空，最大 50 MB'},413)
     filename=parse_qs(parsed.query).get('filename',['roads.json'])[0]
     if Path(filename).suffix.lower() not in ('.json','.geojson','.osm','.xml'):raise ValueError('支持 OSM JSON、.osm / XML 和 GeoJSON')
     self.connection.settimeout(45);content=self.rfile.read(length)
     if len(content)!=length:raise ValueError('上传提前中断')
     source=job/'data/osm_roads_source.json'
     if source.exists():bounds=json.loads(source.read_text())['bounds_wgs84']
     else:
      from app.tracks import parse_track
      state=json.loads((job/'status.json').read_text());bounds=parse_track(job/state['input_file'])[0]['bounds_wgs84']
     import_roads(job,filename,content,bounds)
     report=None
     if (job/'web/metadata.json').exists():
      report=rebuild_roads(job)
      from app.pipeline import package_preview
      package_preview(job)
     return self.json({'saved':True,'roads':report,'message':'道路已导入'})
    finally:
     with LOCK:ACTIVE.discard(job.name)
   if len(parts)==4 and parts[:2]==['api','jobs'] and parts[3]=='retry':
    job=self.job(parts[2]);retry(job);return self.json(json.loads((job/'status.json').read_text()),202)
   if len(parts)==4 and parts[:2]==['api','jobs'] and parts[3]=='houses':
    job=self.job(parts[2])
    with LOCK:
     if job.name in ACTIVE:raise ValueError('请等待当前任务结束再编辑')
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=500000:raise ValueError('判断列表大小无效')
    incoming=json.loads(self.rfile.read(length));existing=json.loads((job/'data/photo_houses.json').read_text());rows=existing['points'];updates={int(x['photo_index']):x for x in incoming['points']}
    if len(updates)!=len(rows) or set(updates)!={x['photo_index'] for x in rows}:raise ValueError('照片编号不匹配')
    for row in rows:
     new=updates[row['photo_index']];value=new['has_house']
     if value is not True and value is not False and value!='uncertain':raise ValueError('has_house 值无效')
     row.update(has_house=value,reason=str(new.get('reason',row['reason']))[:500],source='manual')
    existing['method']='manual';write_json(job/'data/photo_houses.json',existing);return self.json({'saved':True,'message':'已保存；点击重建任务应用到模型'})
   raise FileNotFoundError()
  except (ValueError,KeyError,json.JSONDecodeError) as e:self.json({'error':str(e)},400)
  except FileNotFoundError:self.json({'error':'任务或接口不存在'},404)
  except OSError as e:self.json({'error':str(e)},500)

def serve(port=8765,open_browser=False):
 # A previous process cannot still be running after a fresh service start.
 for p in JOBS.glob('*/status.json'):
  s=json.loads(p.read_text())
  alive=False
  if s.get('worker_pid'):
   try:os.kill(int(s['worker_pid']),0);alive=True
   except PermissionError:alive=True
   except ProcessLookupError:pass
  if s['status'] in ('running','queued') and not alive:
   s.update(status='failed',error='服务上次中断，可重试');write_json(p,s)
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
 print(f'徒步记忆工作台：http://127.0.0.1:{port}/',flush=True)
 if open_browser:
  import webbrowser
  webbrowser.open(f'http://127.0.0.1:{port}/')
 try:server.serve_forever()
 finally:server.server_close();EXECUTOR.shutdown(wait=False)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');args=parser.parse_args()
 try:serve(args.port,args.open)
 except OSError as e:parser.exit(1,f'无法监听 127.0.0.1:{args.port}：{e}。如仍运行旧 http.server，请先在原终端 Ctrl+C，再启动。\n')
