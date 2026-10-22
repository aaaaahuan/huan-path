from pathlib import Path
import json,time,os
STAGES=[('parse','解析轨迹'),('dem','获取地形数据'),('terrain','3D 地形建模'),('features','生成河流与地表要素'),('photos','照片点与房屋'),('scale','海拔刻度'),('export','导出与校验'),('preview','生成网页预览')]
def write_json(path,value):
 path=Path(path);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.replace(temp,path)
class Progress:
 def __init__(self,job):self.job=Path(job);self.path=self.job/'status.json';self.state=json.loads(self.path.read_text())
 def stage(self,key,detail=''):
  now=time.time()
  for s in self.state['stages']:
   if s['status']=='running':s.update(status='done',elapsed_seconds=round(now-s['started_at'],3),finished_at=now)
  stage=next(x for x in self.state['stages'] if x['key']==key);stage.update(status='running',started_at=now,detail=detail,elapsed_seconds=0)
  self.state.update(status='running',updated_at=now);write_json(self.path,self.state)
 def detail(self,text):
  for s in self.state['stages']:
   if s['status']=='running':s['detail']=text
  write_json(self.path,self.state)
 def finish(self,error=None):
  now=time.time()
  for s in self.state['stages']:
   if s['status']=='running':s.update(status='failed' if error else 'done',elapsed_seconds=round(now-s['started_at'],3),finished_at=now)
  self.state.update(status='failed' if error else 'completed',error=error,finished_at=now,total_seconds=round(now-self.state['started_at'],3));write_json(self.path,self.state)
