import unittest,tempfile,zipfile,json
from pathlib import Path
from app.tracks import parse_track,document,geo_tiles
class TrackTests(unittest.TestCase):
 def path(self,text,suffix='.kml'):
  f=tempfile.NamedTemporaryFile(suffix=suffix,delete=False);f.write(text);f.close();self.addCleanup(lambda:Path(f.name).unlink(missing_ok=True));return Path(f.name)
 def test_southern_hemisphere(self):
  p=self.path(b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Sydney &amp; hills</name><Placemark><LineString><coordinates>151.1,-33.9,20 151.12,-33.88,40</coordinates></LineString></Placemark></Document></kml>');info,points,_=parse_track(p);self.assertEqual(info['epsg'],32756);self.assertEqual(info['name'],'Sydney & hills');self.assertEqual(info['photo_points'],[])
 def test_reject_entity(self):
  p=self.path(b'<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><kml/>')
  with self.assertRaises(ValueError):document(p)
 def test_kmz_and_missing_altitude(self):
  p=self.path(b'',suffix='.kmz')
  with zipfile.ZipFile(p,'w') as z:z.writestr('doc.kml','<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString><coordinates>-122.4,37.7 -122.41,37.71</coordinates></LineString></Placemark></Document></kml>');z.writestr('../../unpack-me','not extracted')
  info,_,_=parse_track(p);self.assertTrue(info['missing_altitude']);self.assertEqual(info['epsg'],32610)
 def test_corrupt_and_antimeridian(self):
  p=self.path(b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString><coordinates>179,20,1 -179,20,2</coordinates></LineString></Placemark></Document></kml>')
  with self.assertRaisesRegex(ValueError,'日期变更线'):parse_track(p)
 def test_tile_selection_across_boundaries(self):
  self.assertEqual(set(geo_tiles([98.99,27.99,99.01,28.01],1)),{(27,98),(27,99),(28,98),(28,99)})
if __name__=='__main__':unittest.main()
