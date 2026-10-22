"""Bounded, read-only KML/KMZ parsing and geographic planning."""
from pathlib import Path,PurePosixPath
import json,math,zipfile,xml.etree.ElementTree as ET
from datetime import datetime,timezone,timedelta
import numpy as np
from pyproj import Transformer,Geod
from rasterio.warp import transform_bounds
K='http://www.opengis.net/kml/2.2';G='http://www.google.com/kml/ext/2.2';NS={'k':K,'g':G}
MAX_XML=50_000_000

def document(path):
 path=Path(path)
 if path.suffix.lower()=='.kmz':
  with zipfile.ZipFile(path) as z:
   entries=z.infolist()
   if len(entries)>2500 or sum(x.file_size for x in entries)>800_000_000:raise ValueError('KMZ 解压总量或文件数量超限')
   names=[x.filename for x in entries if x.filename.lower().endswith('.kml')]
   name=next((n for n in names if n.lower()=='doc.kml'),names[0] if len(names)==1 else None)
   if not name:raise ValueError('KMZ 需要 doc.kml 或唯一 KML')
   if z.getinfo(name).file_size>MAX_XML:raise ValueError('KML 超过 50 MB')
   raw=z.read(name)
 else:
  if path.stat().st_size>MAX_XML:raise ValueError('KML 超过 50 MB')
  raw=path.read_bytes()
 if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('不接受 XML DTD/实体')
 return ET.fromstring(raw),raw

def extended(node):return {e.get('name'):e.findtext('k:value',default='',namespaces=NS) for e in node.findall('k:ExtendedData/k:Data',NS)}
def parse_track(path):
 root,raw=document(path);doc=root.find('k:Document',NS)
 if doc is None:doc=root
 ext=extended(doc);segments=[];times=[]
 for track in root.findall('.//g:Track',NS):
  coords=[list(map(float,e.text.split())) for e in track.findall('g:coord',NS)]
  if coords:segments.append(coords);times.extend([e.text for e in track.findall('k:when',NS)])
 if not segments:
  for line in root.findall('.//k:LineString',NS):
   values=line.findtext('k:coordinates',default='',namespaces=NS).split()
   if values:segments.append([list(map(float,s.split(','))) for s in values])
 if not segments or sum(map(len,segments))<2:raise ValueError('未找到可用 gx:Track / LineString')
 missing_alt=any(len(p)<3 for seg in segments for p in seg)
 coords=np.array([(p+[0.]*3)[:3] for seg in segments for p in seg],dtype=float)
 if len(coords)>200000 or not np.isfinite(coords).all():raise ValueError('轨迹点过多或坐标非有限')
 if np.any(abs(coords[:,0])>180) or np.any(abs(coords[:,1])>84):raise ValueError('仅支持经度±180、UTM 纬度 -80 至 84 范围')
 if coords[:,1].min()<-80 or np.ptp(coords[:,0])>180:raise ValueError('暂不支持极地或跨日期变更线轨迹')
 lon,lat=coords[:,:2].mean(axis=0);zone=max(1,min(60,int((lon+180)//6)+1));epsg=(32600 if lat>=0 else 32700)+zone
 tf=Transformer.from_crs(4326,epsg,always_xy=True);x,y=tf.transform(coords[:,0],coords[:,1]);xy=np.column_stack((x,y))
 lo=xy.min(axis=0)-1100;hi=xy.max(axis=0)+1100
 if (hi-lo).max()>200000:raise ValueError('本地原型限制模型跨度为 200 km；请裁剪轨迹后重试')
 bounds=list(transform_bounds(epsg,4326,*lo,*hi,densify_pts=21))
 _,_,distances=Geod(ellps='WGS84').inv(coords[:-1,0],coords[:-1,1],coords[1:,0],coords[1:,1])
 begin=ext.get('BeginTime');date=''
 try:date=datetime.fromtimestamp(int(begin)/1000,timezone(timedelta(hours=8))).date().isoformat()
 except (TypeError,ValueError,OverflowError):
  if times:date=times[0][:10]
 def number(key):
  try:return float(ext[key])
  except (KeyError,ValueError):return None
 name=doc.findtext('k:name',default='',namespaces=NS) or Path(path).stem
 photos=[]
 for pm in root.findall('.//k:Placemark',NS):
  point=pm.findtext('k:Point/k:coordinates',default='',namespaces=NS)
  if not point:continue
  if 'MarkerStylePicture' not in pm.findtext('k:styleUrl',default='',namespaces=NS):continue
  data=extended(pm);fid=data.get('FileId','')
  if not fid.isdigit():continue
  values=list(map(float,point.strip().split(',')))
  if len(values)<2 or not np.isfinite(values).all() or abs(values[0])>180 or abs(values[1])>90:raise ValueError('照片标注点坐标无效')
  photos.append({'index':len(photos)+1,'file_id':fid,'longitude':values[0],'latitude':values[1],'recorded_altitude_m':values[2] if len(values)>2 else None,'timestamp_ms':data.get('Time'),'name':pm.findtext('k:name',default='',namespaces=NS),'note':data.get('description','') or ''})
 info={'name':name,'date':date,'start_name':ext.get('PosStartName') or '起点','end_name':ext.get('PosEndName') or '终点','recorded_distance_km':(number('Distance') or number('Mileage') or sum(distances))/1000,'calculated_distance_km':float(sum(distances)/1000),'point_count':len(coords),'epsg':epsg,'utm_zone':zone,'hemisphere':'N' if lat>=0 else 'S','bounds_wgs84':bounds,'bounds_projected':[*lo.tolist(),*hi.tolist()],'photo_points':photos,'segments':list(map(len,segments)),'missing_altitude':missing_alt,'warnings':['多个 Track 段按导出顺序连接，段间停录空隙可能形成连接线'] if len(segments)>1 else []}
 return info,coords,raw

def canonical(coords,path):
 root=ET.Element('{'+K+'}kml');doc=ET.SubElement(root,'{'+K+'}Document');t=ET.SubElement(doc,'{'+G+'}Track')
 for p in coords:ET.SubElement(t,'{'+G+'}coord').text=' '.join(str(float(x)) for x in p)
 ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)

def geo_tiles(bounds,step):
 west,south,east,north=bounds
 return [(y,x) for y in range(math.floor(south/step)*step,math.floor(north/step)*step+1,step) for x in range(math.floor(west/step)*step,math.floor(east/step)*step+1,step)]
