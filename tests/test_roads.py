import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pyproj import Transformer
from app import datasets,roads

class RoadsTests(unittest.TestCase):
 def test_classes(self):
  for group,values in {'major':['motorway','trunk_link','primary_link'],'secondary':['secondary','tertiary_link'],'local':['residential','unclassified','service','living_street'],'trail':['track','path','footway','bridleway','steps','cycleway']}.items():
   for value in values:self.assertEqual(roads.classify(value),group)
  self.assertIsNone(roads.classify('construction'))
 def test_bbox_cache(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   def fetch(url,target,*args,**kwargs):Path(target).write_text('{"elements": []}')
   with patch.object(datasets,'fetch',side_effect=fetch) as request:
    first,source=datasets.overpass([98,28,99,29],highway=True)
    self.assertIn('way["highway"]',source['query'])
    self.assertTrue(datasets.overpass([98,28,99,29],highway=True)[1]['cache_hit'])
    self.assertEqual(request.call_count,1)
    datasets.overpass([98,28,99,30],highway=True)
    self.assertEqual(request.call_count,2)
 def test_failure(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(roads,'overpass',side_effect=TimeoutError('timeout')):
   warnings=[];raw=roads.prepare_roads(tmp,[98,28,99,29],warnings)
   self.assertEqual(raw['elements'],[]);self.assertEqual(len(warnings),1)
   self.assertFalse(json.loads((Path(tmp)/'osm_roads_source.json').read_text())['available'])
 def test_clipped_ribbons(self):
  raw={'elements':[{'type':'way','tags':{'highway':'path'},'geometry':[{'lon':-1,'lat':5},{'lon':12,'lat':5}]}]}
  with tempfile.TemporaryDirectory() as tmp:
   result=roads.build_roads(raw,Transformer.from_crs(4326,4326,always_xy=True),np.array([0,0]),np.array([10,10]),1,tmp)
   self.assertEqual(result['count'],1)
   v=np.fromfile(Path(tmp)/'layers/roads_trail.bin',dtype='<f4').reshape(-1,3)
   self.assertTrue(np.all((v[:,:2]>=0)&(v[:,:2]<=10)))
   self.assertGreater(len(v),100)
if __name__=='__main__':unittest.main()
