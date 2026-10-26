import json,tempfile,time,unittest,os
from pathlib import Path
from unittest.mock import patch
from app import datasets,roads
from app.road_import import parse_roads,intersects

DOC={'elements':[{'type':'node','id':1,'lon':98,'lat':28},{'type':'node','id':2,'lon':98.1,'lat':28.1},{'type':'way','id':9,'nodes':[1,2],'tags':{'highway':'path'}},{'type':'way','id':10,'nodes':[1,2],'tags':{'building':'yes'}}]}
class SourcesTests(unittest.TestCase):
 def test_proxy(self):
  with patch.dict(os.environ,{'HTTPS_PROXY':'http://env:8','https_proxy':'http://lower:8','ALL_PROXY':'http://all:8'},clear=True):
   self.assertEqual(datasets.resolve_proxy('https://osm.org',{'network':{'proxy':'http://config:8'}}),('http://config:8','config'))
   self.assertEqual(datasets.resolve_proxy('https://osm.org',{'proxy':'off'}),(None,'config:off'))
   self.assertEqual(datasets.resolve_proxy('https://osm.org',{}),('http://env:8','env:HTTPS_PROXY'))
   self.assertEqual(datasets.resolve_proxy('http://127.0.0.1',{}),(None,'loopback'))
  with patch.dict(os.environ,{},clear=True),patch.object(datasets.sys,'platform','darwin'),patch.object(datasets.urllib.request,'getproxies',return_value={'https':'http://user:secret@127.0.0.1:7897'}):
   self.assertEqual(datasets.resolve_proxy('https://osm.org',{})[1],'macOS system')
   self.assertNotIn('secret',str(datasets.proxy_record('https://osm.org')))
 def test_curl_proxy_and_timeout(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'resolve_proxy',return_value=('http://user:secret@proxy:8','config')):
   with patch.object(datasets.subprocess,'run',side_effect=subprocess.TimeoutExpired(['curl','http://user:secret@proxy:8'],1)):
    with self.assertRaises(RuntimeError) as caught:datasets.fetch('https://osm.org',Path(tmp)/'data',timeout=1)
    self.assertNotIn('secret',str(caught.exception))
   def run(cmd,**kwargs):
    self.assertIn('-K',cmd);self.assertNotIn('http://user:secret@proxy:8',str(cmd));self.assertEqual(kwargs['input'],'proxy = "http://user:secret@proxy:8"\n');self.assertEqual(cmd[cmd.index('--max-time')+1],'3')
    Path(cmd[cmd.index('-o')+1]).write_text('{}')
    return subprocess.CompletedProcess(cmd,0,'','')
   with patch.object(datasets.subprocess,'run',side_effect=run):datasets.fetch('https://osm.org',Path(tmp)/'data',timeout=3)
 def test_proxy_stdin_escaping_and_error(self):
  import subprocess
  proxy='http://user:se"c\\ret@proxy:8'
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'resolve_proxy',return_value=(proxy,'config')):
   def run(cmd,**kwargs):
    self.assertNotIn(proxy,str(cmd))
    self.assertEqual(kwargs['input'],'proxy = "'+proxy.replace('\\','\\\\').replace('"','\\"')+'"\n')
    return subprocess.CompletedProcess(cmd,22,'','curl: (22) The requested URL returned error: 400 '+proxy)
   with patch.object(datasets.subprocess,'run',side_effect=run):
    with self.assertRaisesRegex(RuntimeError,'HTTP 400') as error:datasets.fetch('https://osm.org',Path(tmp)/'data')
    self.assertNotIn(proxy,str(error.exception))
 def test_formats(self):
  for content in [json.dumps(DOC).encode(),b'<osm><node id="1" lon="98" lat="28"/><node id="2" lon="98.1" lat="28.1"/><way id="9"><nd ref="1"/><nd ref="2"/><tag k="highway" v="path"/></way></osm>',json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'MultiLineString','coordinates':[[[98,28],[98.1,28.1]]]}}]}).encode()]:
   doc=parse_roads(content);self.assertEqual(len(doc['elements']),1);self.assertEqual(doc['elements'][0]['tags']['highway'],'path');self.assertTrue(intersects(doc,[97,27,99,29]));self.assertFalse(intersects(doc,[0,0,1,1]))
  self.assertEqual(parse_roads(json.dumps(parse_roads(json.dumps(DOC).encode())).encode())['elements'][0]['id'],9)
  for bad in [b'bad',b'null',b'[]',b'<osm>',b'{"type":"Point"}',b'<!DOCTYPE x><osm/>']:
   with self.assertRaises(ValueError):parse_roads(bad)
 def test_main_fallback(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   def fetch(url,target,*args,**kwargs):
    if 'interpreter' in url:raise RuntimeError('mock 502')
    Path(target).write_text(json.dumps(DOC))
   with patch.object(datasets,'fetch',side_effect=fetch) as req:
    doc,source=datasets.overpass([98,28,98.2,28.2],highway=True)
    self.assertEqual(len(doc['elements']),1);self.assertEqual(source['source_type'],'osm_api');self.assertEqual(len(source['previous_errors']),4);self.assertEqual(req.call_count,5)
    self.assertEqual(datasets.overpass([98,28,98.2,28.2],highway=True)[1]['source_type'],'osm_api')
 def test_failed_writer_preserves_shared_cache(self):
  import hashlib
  bounds=[98,28,98.2,28.2]
  query='[out:json][timeout:25];(way["highway"](28.0000000,98.0000000,28.2000000,98.2000000););out body geom;'
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   cached=Path(tmp)/('osm-'+hashlib.sha256(query.encode()).hexdigest()[:24]+'.json')
   def failed(*args,**kwargs):
    datasets.cache_json(cached,{'elements':[]})
    raise RuntimeError('mock second job failure')
   with patch.object(datasets,'fetch',side_effect=failed),patch.object(datasets,'osm_map',side_effect=RuntimeError('mock failure')):
    with self.assertRaises(RuntimeError):datasets.overpass(bounds,highway=True)
   self.assertTrue(cached.exists());self.assertTrue(datasets.overpass(bounds,highway=True)[1]['cache_hit'])
 def test_legacy_local_cache_ignored(self):
  import hashlib
  bounds=[98,28,98.2,28.2]
  query='[out:json][timeout:25];(way["highway"](28.0000000,98.0000000,28.2000000,98.2000000););out body geom;'
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   cached=Path(tmp)/('osm-'+hashlib.sha256(query.encode()).hexdigest()[:24]+'.json')
   datasets.cache_json(cached,DOC);datasets.cache_json(cached.with_suffix('.source.json'),{'source_type':'local'})
   def fetch(url,target,*args,**kwargs):Path(target).write_text(json.dumps({'elements':[]}))
   with patch.object(datasets,'fetch',side_effect=fetch) as online:
    self.assertEqual(datasets.overpass(bounds,highway=True)[1]['source_type'],'overpass');online.assert_called_once()
 def test_tile_merge(self):
  def fetch(url,target,*args,**kwargs):Path(target).write_text(json.dumps(DOC))
  with patch.object(datasets,'fetch',side_effect=fetch) as req:
   doc=datasets.osm_map([98,28,99,29],time.monotonic()+10);self.assertEqual(req.call_count,4);self.assertEqual(len(doc['elements']),1);self.assertEqual(len(doc['elements'][0]['geometry']),2)
 def test_overdense_split(self):
  calls=[]
  def fetch(url,target,params,**kwargs):
   calls.append(params)
   if len(calls)==1:raise RuntimeError('HTTP 400')
   Path(target).write_text(json.dumps(DOC))
  with patch.object(datasets,'fetch',side_effect=fetch):self.assertEqual(datasets.osm_map([98,28,98.4,28.4],time.monotonic()+10)['map_tiles'],2)
 def test_rate_limit_no_split(self):
  with patch.object(datasets,'fetch',side_effect=RuntimeError('HTTP 509')) as fetch:
   with self.assertRaisesRegex(RuntimeError,'509'):datasets.osm_map([98,28,98.4,28.4],time.monotonic()+10)
   self.assertEqual(fetch.call_count,1)
 def test_bom_and_missing_nodes(self):
  incomplete={'type':'way','id':99,'nodes':[1,999],'tags':{'highway':'path'}}
  doc=parse_roads(b'\xef\xbb\xbf'+json.dumps({'elements':DOC['elements']+[incomplete]}).encode())
  self.assertEqual(len(doc['elements']),1)
  self.assertEqual(len(parse_roads(b'\xef\xbb\xbf <osm><way id="1"><nd lat="28" lon="98"/><nd lat="28.1" lon="98.1"/><tag k="highway" v="path"/></way></osm>')['elements']),1)
 def test_budget(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)),patch.object(datasets.time,'monotonic',side_effect=[0]+[datasets.OVERPASS_BUDGET+datasets.OSM_API_RESERVE+1]*5),patch.object(datasets,'fetch') as fetch:
   with self.assertRaises(RuntimeError):datasets.overpass([98,28,99,29],highway=True)
   fetch.assert_not_called()
 def test_import_priority_cache(self):
  with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cache,patch.object(datasets,'CACHE',Path(cache)),patch.object(roads,'overpass') as online:
   job=Path(tmp);(job/'data').mkdir();bounds=[97,27,99,29]
   roads.import_roads(job,'local.json',json.dumps(DOC).encode(),bounds)
   self.assertEqual(len(roads.prepare_roads(job/'data',bounds,[])['elements']),1);online.assert_not_called()
   self.assertEqual(list(Path(cache).iterdir()),[])
   with self.assertRaisesRegex(ValueError,'不相交'):roads.import_roads(job,'bad.json',json.dumps(DOC).encode(),[0,0,1,1])
 def test_width_hierarchy(self):
  styles=list(roads.STYLES.values())
  for units in [.01,.5,1,10]:
   widths=[min(s['max_mm'],max(s['width_mm'],s['min_px']*units)) for s in styles]
   self.assertEqual(widths,sorted(widths,reverse=True));self.assertEqual(len(set(widths)),4)
if __name__=='__main__':unittest.main()
