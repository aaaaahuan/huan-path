"""Validated local OSM JSON/XML and GeoJSON road normalization."""
import re,json,math,xml.etree.ElementTree as ET
from shapely.geometry import LineString,box
MAX_SIZE=50_000_000

def way_geometry(way,nodes):
 """Normalize complete ways; never bridge gaps caused by missing nodes."""
 geometry=way.get('geometry')
 ids=way.get('nodes',[])
 if geometry:
  if ids and len(geometry)!=len(ids):return None
 else:
  if len(ids)<2 or any(i not in nodes for i in ids):return None
  geometry=[nodes[i] for i in ids]
 if len(geometry)<2:return None
 return [{'lon':p['lon'],'lat':p['lat']} for p in geometry]

def parse_roads(content):
 if not 0<len(content)<=MAX_SIZE:raise ValueError('道路文件不能为空，最大 50 MB')
 content=content.removeprefix(b'\xef\xbb\xbf').lstrip()
 try:
  if content.lstrip().startswith(b'<'):
   if re.search(rb'<!(DOCTYPE|ENTITY)',content,re.I):raise ValueError('道路 XML 不接受 DTD/ENTITY')
   root=ET.fromstring(content);elements=[]
   for el in root:
    if el.tag=='node':elements.append({'type':'node','id':int(el.attrib['id']),'lat':float(el.attrib['lat']),'lon':float(el.attrib['lon'])})
    elif el.tag=='way':elements.append({'type':'way','id':int(el.attrib['id']),'nodes':[int(x.attrib['ref']) for x in el.findall('nd') if 'ref' in x.attrib],'tags':{x.attrib['k']:x.attrib['v'] for x in el.findall('tag')},'geometry':[{'lat':float(x.attrib['lat']),'lon':float(x.attrib['lon'])} for x in el.findall('nd') if 'lat' in x.attrib]})
   doc={'elements':elements}
  else:doc=json.loads(content)
  if not isinstance(doc,dict):raise ValueError('道路文件顶层需要 JSON 对象')
  result=[]
  if doc.get('type') in ('FeatureCollection','Feature'):
   for feature in doc.get('features',[doc]):
    g=feature.get('geometry') or {};kind=g.get('type');coords=g.get('coordinates',[])
    if kind not in ('LineString','MultiLineString'):continue
    for line in ([coords] if kind=='LineString' else coords):result.append({'type':'way','id':len(result)+1,'tags':{'highway':(feature.get('properties') or {}).get('highway') or 'path'},'geometry':[{'lon':p[0],'lat':p[1]} for p in line]})
  elif 'elements' in doc:
   nodes={el['id']:el for el in doc['elements'] if el.get('type')=='node'}
   for el in doc['elements']:
    if el.get('type')!='way' or not el.get('tags',{}).get('highway'):continue
    geom=way_geometry(el,nodes)
    if geom is None:continue
    result.append({'type':'way','id':el.get('id',len(result)+1),'tags':el['tags'],'geometry':[{'lon':p['lon'],'lat':p['lat']} for p in geom]})
  else:raise ValueError('需要 OSM JSON/XML 或 GeoJSON 线要素')
  for el in result:
   if not isinstance(el['tags']['highway'],str):raise ValueError('highway 必须为文本')
   if len(el['geometry'])<2:raise ValueError('道路至少需要两个坐标')
   for p in el['geometry']:
    if not all(isinstance(p[k],(int,float)) and math.isfinite(p[k]) and abs(p[k])<=limit for k,limit in [('lon',180),('lat',90)]):raise ValueError('道路坐标无效')
  if not result:raise ValueError('文件中没有道路线要素')
  return {'elements':result}
 except (KeyError,TypeError,AttributeError,RecursionError,ET.ParseError,json.JSONDecodeError,IndexError) as ex:raise ValueError('道路文件解析失败：'+str(ex)) from ex

def intersects(raw,bounds):
 return any(LineString([(p['lon'],p['lat']) for p in el['geometry']]).intersects(box(*bounds)) for el in raw['elements'])
