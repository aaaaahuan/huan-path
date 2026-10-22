import tempfile,unittest,json
from pathlib import Path
import numpy as np
from elevation_scale import build_scale
class ScaleLayout(unittest.TestCase):
 def test_equal_endpoint_altitudes_do_not_overprint(self):
  cfg=json.loads(Path('config/features.json').read_text())['elevation_scale']
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'web/layers').mkdir(parents=True)
   solid,report=build_scale(cfg,np.full((4,10),20.),[200,100],[300,500],.02,4,1.25,root,np.array([300,300]))
   self.assertTrue(solid.volume()>0);self.assertEqual(len({t['local_u_mm'] for t in report['ticks']}),4);self.assertTrue(all(t['display_z_mm']==4 and not t['relocated'] for t in report['ticks']))
if __name__=='__main__':unittest.main()
