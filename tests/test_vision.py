import unittest,tempfile,os
from pathlib import Path
from unittest.mock import patch,Mock
from app.photos import vision_house
class VisionContract(unittest.TestCase):
 def test_responses_image_and_json_contract(self):
  with tempfile.NamedTemporaryFile(suffix='.jpg') as f:
   f.write(b'test image');f.flush()
   response=Mock(ok=True);response.json.return_value={'output':[{'content':[{'type':'output_text','text':'{"has_house":"uncertain","reason":"distant"}'}]}]}
   with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_VISION_MODEL':'test-vision'}),patch('requests.post',return_value=response) as post:
    result=vision_house(f.name);self.assertEqual(result['has_house'],'uncertain');payload=post.call_args.kwargs['json'];self.assertEqual(payload['model'],'test-vision');self.assertTrue(payload['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'));self.assertTrue(payload['text']['format']['strict'])
if __name__=='__main__':unittest.main()
