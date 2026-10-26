import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import datasets

class Clock:
 """Fake monotonic clock; a mocked fetch that 'hangs' advances it by its whole timeout."""
 def __init__(self):self.t=0.
 def __call__(self):return self.t

class OverpassTimeoutTests(unittest.TestCase):
 def setUp(self):datasets._slow_endpoints.clear()
 tearDown=setUp
 def test_server_and_client_timeouts(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   seen=[]
   def fetch(url,target,params,timeout):seen.append((params['data'],timeout));Path(target).write_text('{"elements": []}')
   with patch.object(datasets,'fetch',side_effect=fetch):doc,source=datasets.overpass([120,30,120.1,30.1])
   query,timeout=seen[0]
   self.assertTrue(query.startswith(f'[out:json][timeout:{datasets.OVERPASS_SERVER_TIMEOUT}];'))
   self.assertGreaterEqual(datasets.OVERPASS_SERVER_TIMEOUT,90);self.assertGreater(timeout,datasets.OVERPASS_SERVER_TIMEOUT);self.assertEqual(timeout,datasets.OVERPASS_ATTEMPT)
   self.assertEqual(source['query'],query)
 def test_cache_key_survives_timeout_change(self):
  body='(way["highway"](28.0000000,98.0000000,28.2000000,98.2000000););out body geom;'
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)):
   cached=Path(tmp)/('osm-'+hashlib.sha256(('[out:json][timeout:25];'+body).encode()).hexdigest()[:24]+'.json')
   datasets.cache_json(cached,{'elements':[{'type':'way','id':1}]});datasets.cache_json(cached.with_suffix('.source.json'),{'source_type':'overpass'})
   with patch.object(datasets,'fetch') as fetch:
    doc,source=datasets.overpass([98,28,98.2,28.2],highway=True)
   fetch.assert_not_called();self.assertTrue(source['cache_hit']);self.assertEqual(len(doc['elements']),1)
 def test_slow_success_within_attempt(self):
  # 48 s response (measured for Hangzhou) must succeed on the first mirror that answers.
  clock=Clock()
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)),patch.object(datasets.time,'monotonic',clock):
   def fetch(url,target,params,timeout):
    if timeout<48:clock.t+=timeout;raise RuntimeError('curl exit 28')
    clock.t+=48;Path(target).write_text('{"elements": [{"type":"node","id":1}]}')
   with patch.object(datasets,'fetch',side_effect=fetch) as f:doc,source=datasets.overpass([120,30,120.1,30.1])
   self.assertEqual(f.call_count,1);self.assertEqual(source['endpoint'],'https://overpass.kumi.systems/api/interpreter')
 def test_worst_case_budget_not_multiplied(self):
  for wide in (False,True):
   datasets._slow_endpoints.clear();clock=Clock()
   with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)),patch.object(datasets.time,'monotonic',clock):
    calls=[]
    def fetch(url,target,params=None,timeout=0):calls.append((url,timeout));clock.t+=timeout;raise RuntimeError('curl exit 28')
    with patch.object(datasets,'fetch',side_effect=fetch),patch.object(datasets,'osm_map',side_effect=lambda b,deadline,keep=None:(_ for _ in ()).throw(TimeoutError('budget'))):
     with self.assertRaises(Exception):datasets.overpass([120,30,120.1,30.1],highway=wide)
    total=datasets.OVERPASS_BUDGET+(datasets.OSM_API_RESERVE if wide else 0)
    self.assertLessEqual(clock.t,total+.01)
    overpass_time=sum(t for u,t in calls if 'interpreter' in u)
    self.assertLessEqual(overpass_time,datasets.OVERPASS_BUDGET+.01)
    self.assertTrue(all(t>=datasets.OVERPASS_MIN_ATTEMPT for u,t in calls))
    self.assertEqual(calls[0][0],'https://overpass.kumi.systems/api/interpreter')  # configured order kept
 def test_timed_out_mirror_tried_last_next_query(self):
  clock=Clock();order=[]
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)),patch.object(datasets.time,'monotonic',clock):
   def fetch(url,target,params,timeout):
    order.append(url)
    if 'kumi' in url:clock.t+=timeout;raise RuntimeError('curl exit 28')
    if 'coffee' in url:raise RuntimeError('HTTP 502')  # fast failure: not demoted
    Path(target).write_text('{"elements": []}')
   with patch.object(datasets,'fetch',side_effect=fetch):
    datasets.overpass([120,30,120.1,30.1]);first=list(order);order.clear()
    datasets.overpass([120,30,120.1,30.2])
  self.assertEqual([u.split('/')[2] for u in first],['overpass.kumi.systems','overpass.private.coffee','overpass-api.de'])
  self.assertEqual([u.split('/')[2] for u in order],['overpass.private.coffee','overpass-api.de'])
 def test_budget_truncated_try_not_demoted(self):
  # Full-length timeouts demote a mirror; the last, budget-shortened try says nothing about its mirror.
  clock=Clock()
  with tempfile.TemporaryDirectory() as tmp,patch.object(datasets,'CACHE',Path(tmp)),patch.object(datasets.time,'monotonic',clock):
   calls=[]
   def fetch(url,target,params,timeout):calls.append(timeout);clock.t+=timeout;raise RuntimeError('curl exit 28')
   with patch.object(datasets,'fetch',side_effect=fetch),self.assertRaises(Exception):datasets.overpass([120,30,120.1,30.1])
  self.assertEqual(len(calls),3);self.assertLess(calls[-1],datasets.OVERPASS_ATTEMPT)
  self.assertEqual({u.split('/')[2] for u in datasets._slow_endpoints},{'overpass.kumi.systems','overpass.private.coffee'})
if __name__=='__main__':unittest.main()
