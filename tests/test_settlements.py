import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pyproj import Transformer
from app import datasets,settlements

IDENT=Transformer.from_crs(4326,4326,always_xy=True)
def square(x0,y0,x1,y1):return [{'lon':x0,'lat':y0},{'lon':x1,'lat':y0},{'lon':x1,'lat':y1},{'lon':x0,'lat':y1},{'lon':x0,'lat':y0}]
RAW={'elements':[
 {'type':'node','id':1,'lon':5,'lat':5,'tags':{'place':'town','name':'Yubeng','name:zh':'雨崩','population':'1,200'}},
 {'type':'node','id':2,'lon':2,'lat':8,'tags':{'place':'hamlet','name':'Upper'}},
 {'type':'node','id':3,'lon':3,'lat':3,'tags':{'place':'village'}},  # unnamed: never invented
 {'type':'node','id':4,'lon':50,'lat':50,'tags':{'place':'city','name':'Far'}},  # outside model
 {'type':'node','id':5,'lon':4,'lat':4,'tags':{'place':'suburb','name':'Ignored kind'}},
 {'type':'way','id':10,'tags':{'landuse':'residential'},'geometry':square(1,1,4,4)},
 {'type':'way','id':11,'tags':{'landuse':'industrial'},'geometry':square(6,6,9,9)},
 {'type':'way','id':12,'tags':{'landuse':'retail'},'geometry':[{'lon':6,'lat':1},{'lon':8,'lat':1}]},  # open way: no area
 {'type':'relation','id':20,'tags':{'landuse':'commercial'},'members':[
   {'type':'way','role':'outer','geometry':square(6,1,9,4)},
   {'type':'way','role':'inner','geometry':square(7,2,8,3)}]},
]}

class SettlementTests(unittest.TestCase):
 def build(self,raw,tmp,grid=(11,11)):
  return settlements.build_settlements(raw,IDENT,np.array([0.,0.]),np.array([10.,10.]),1,tmp,grid)
 def test_labels_and_areas(self):
  with tempfile.TemporaryDirectory() as tmp:
   report=self.build(RAW,tmp,(21,21))
   self.assertTrue(report['preview_only'])
   doc=json.loads((Path(tmp)/'layers/places.json').read_text())
   self.assertEqual([r['name'] for r in doc['labels']],['雨崩','Upper'])  # rank order, name:zh preferred
   self.assertEqual(doc['labels'][0]['population'],1200);self.assertEqual(doc['labels'][0]['name_source'],'Yubeng')
   self.assertEqual(report['places']['counts']['town'],1);self.assertEqual(report['places']['counts']['city'],0)
   cells=np.fromfile(Path(tmp)/'layers/settlements.bin',dtype='u1').reshape(21,21)
   # 0.5 mm cells; row 0 is south (y=0) like classes.bin. Index = coordinate*2.
   self.assertEqual(cells[4,4],1)    # (2,2) residential
   self.assertEqual(cells[14,14],3)  # (7,7) industrial
   self.assertEqual(cells[3,13],2)   # (6.5,1.5) commercial outer ring
   self.assertEqual(cells[5,15],0)   # (7.5,2.5) inner hole stays empty
   self.assertEqual(cells[0,0],0);self.assertEqual(cells[18,2],0)
   self.assertEqual(report['areas']['polygons'],{'industrial':1,'commercial':1,'residential':1})
 def test_empty_removes_stale_layers(self):
  with tempfile.TemporaryDirectory() as tmp:
   self.build(RAW,tmp);report=self.build({'elements':[]},tmp)
   self.assertIsNone(report['places']['url']);self.assertIsNone(report['areas']['url'])
   self.assertFalse((Path(tmp)/'layers/places.json').exists());self.assertFalse((Path(tmp)/'layers/settlements.bin').exists())
 def test_failure_degrades_with_warning(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(settlements,'overpass',side_effect=TimeoutError('timeout')):
   warnings=['聚落数据获取失败 old'];raw=settlements.prepare_settlements(tmp,[98,28,99,29],warnings)
   self.assertEqual(raw['elements'],[]);self.assertEqual(len(warnings),1);self.assertIn('timeout',warnings[0])
   source=json.loads((Path(tmp)/'osm_settlements_source.json').read_text())
   self.assertFalse(source['available']);self.assertEqual(source['license'],'ODbL 1.0')
 def test_overpass_query_cache_and_osm_api_fallback(self):
  api={'elements':[{'type':'node','id':1,'lat':28.1,'lon':98.1,'tags':{'place':'village','name':'A'}},{'type':'node','id':2,'lat':28.1,'lon':98.2},
   {'type':'node','id':3,'lat':28.2,'lon':98.2},{'type':'node','id':4,'lat':28.2,'lon':98.1},{'type':'node','id':9,'lat':28.3,'lon':98.3,'tags':{'amenity':'cafe'}},
   {'type':'way','id':7,'nodes':[1,2,3,4,1],'tags':{'landuse':'residential'}},{'type':'way','id':8,'nodes':[1,2],'tags':{'highway':'path'}}]}
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   calls=[]
   def fetch(url,target,*args,**kwargs):
    calls.append(url)
    if 'interpreter' in url:raise RuntimeError('mock 504')
    Path(target).write_text(json.dumps(api))
   with patch.object(datasets,'fetch',side_effect=fetch):
    doc,source=datasets.overpass([98,28,98.25,28.25],settlement=True)
    self.assertEqual(source['source_type'],'osm_api')
    self.assertIn('node[place~"^(city|town|village|hamlet|locality)$"]',source['query'])
    kinds=sorted((e['type'],e['id']) for e in doc['elements'])
    self.assertEqual(kinds,[('node',1),('way',7)])  # no highway/cafe leakage
    self.assertTrue(datasets.overpass([98,28,98.25,28.25],settlement=True)[1]['cache_hit'])
    n=len(calls);datasets.overpass([98,28,98.25,28.25],settlement=True);self.assertEqual(len(calls),n)
    report=settlements.build_settlements(doc,Transformer.from_crs(4326,32647,always_xy=True),*(lambda t:(np.array(t.transform(98,28)),np.array(t.transform(98.25,28.25))))(Transformer.from_crs(4326,32647,always_xy=True)),.001,tmp,(30,30))
    self.assertEqual(report['places']['count'],1);self.assertGreater(report['areas']['cells']['residential'],0)
 def test_highway_osm_api_unchanged(self):
  doc={'elements':[{'type':'node','id':1,'lat':28.1,'lon':98.1,'tags':{'place':'village','name':'A'}},{'type':'node','id':2,'lat':28.1,'lon':98.2},{'type':'way','id':8,'nodes':[1,2],'tags':{'highway':'path'}}]}
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   def fetch(url,target,*args,**kwargs):
    if 'interpreter' in url:raise RuntimeError('mock 504')
    Path(target).write_text(json.dumps(doc))
   with patch.object(datasets,'fetch',side_effect=fetch):
    out,_=datasets.overpass([98,28,98.25,28.25],highway=True)
    self.assertEqual([(e['type'],e['id']) for e in out['elements']],[('way',8)])
 def test_rebuild_existing_work_preview_only(self):
  """Copies a minimal work into a temp dir; models/*.stl/3mf bytes must stay identical."""
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp)/'job';(job/'data').mkdir(parents=True);(job/'web/layers').mkdir(parents=True);(job/'models').mkdir()
   t=Transformer.from_crs(4326,32647,always_xy=True);lo=np.array(t.transform(98.0,28.0));hi=lo+np.array([2000.,1500.])
   meta={'features':{'model_extent_projected_m':[*lo.tolist(),*hi.tolist()]},'preview_layers':{'grid':[21,16],'available':{'roads':False}},'sources':{},'warnings':[]}
   (job/'web/metadata.json').write_text(json.dumps(meta));(job/'models/validation.json').write_text(json.dumps(meta))
   (job/'spec.json').write_text(json.dumps({'route':{'epsg':32647},'model':{'size_mm':200,'padding_m':1100},'warnings':[]}))
   (job/'models/terrain.stl').write_bytes(b'solid');(job/'models/terrain.3mf').write_bytes(b'PK3mf')
   lon,lat=Transformer.from_crs(32647,4326,always_xy=True).transform(*(lo+500))
   raw={'elements':[{'type':'node','id':1,'lon':lon,'lat':lat,'tags':{'place':'village','name':'测试村'}}]}
   with patch.object(settlements,'overpass',return_value=(raw,{'cache_hit':False,'source_type':'overpass'})):
    report=settlements.rebuild_settlements(job)
   self.assertEqual(report['places']['count'],1)
   meta=json.loads((job/'web/metadata.json').read_text())
   self.assertTrue(meta['preview_layers']['available']['places']);self.assertFalse(meta['preview_layers']['available']['settlements'])
   self.assertEqual(meta['sources']['settlements']['license'],'ODbL 1.0')
   self.assertEqual((job/'models/terrain.stl').read_bytes(),b'solid');self.assertEqual((job/'models/terrain.3mf').read_bytes(),b'PK3mf')
   label=json.loads((job/'web/layers/places.json').read_text())['labels'][0]
   self.assertAlmostEqual(label['x_mm'],50,delta=.01);self.assertAlmostEqual(label['y_mm'],50,delta=.01)
 def test_empty_report_clears_stale_layers(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'layers').mkdir();(Path(tmp)/'layers/places.json').write_text('{}');(Path(tmp)/'layers/settlements.bin').write_bytes(b'1')
   report=settlements.empty_report(tmp,(5,4))
   self.assertIsNone(report['places']['url']);self.assertIsNone(report['areas']['url']);self.assertEqual(report['areas']['grid'],[5,4])
   self.assertFalse((Path(tmp)/'layers/places.json').exists());self.assertFalse((Path(tmp)/'layers/settlements.bin').exists())
   meta={'preview_layers':{'available':{}}};settlements.apply_report(meta,report,{'available':False})
   self.assertFalse(meta['preview_layers']['available']['places']);self.assertFalse(meta['preview_layers']['available']['settlements'])
 def test_build_model_settlements_after_export_and_guarded(self):
  """Preview layers must never block print files: built after STL/3MF export, inside try/except."""
  src=(Path(__file__).resolve().parents[1]/'build_model.py').read_text()
  at=src.index('prepare_settlements(DATA');self.assertGreater(at,src.index("mesh.export(OUT/'models/"));self.assertGreater(at,src.index("ZipFile(OUT/'models/"))
  block=src[src.rindex('\ntry:',0,at):src.index('apply_settlements(report',at)];self.assertIn('except Exception',block);self.assertIn('empty_report(',block)
if __name__=='__main__':unittest.main()
