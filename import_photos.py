"""Import the Jan 27 photo waypoints without touching printing geometry or source files."""
from pathlib import Path
import hashlib,io,json,shutil,zipfile,xml.etree.ElementTree as ET
from datetime import datetime,timezone,timedelta
import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from PIL import Image,ImageOps
R=Path(__file__).resolve().parent
KMZ=Path('/Users/huan/Desktop/paths/2026-01-27-yubeng.kmz')
KML=Path('/Users/huan/Desktop/paths/2026-01-27-yubeng.kml')
D=R/'data/photos-2026-01-27';W=R/'web/photos';(D/'originals').mkdir(parents=True,exist_ok=True);(W/'thumbs').mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.relative_to(R)):sha(p) for p in (R/'models').glob('*') if p.suffix in ('.stl','.3mf')}
source_hashes={str(p):sha(p) for p in [KMZ,KML]}
shutil.copyfile(KMZ,D/'source.kmz');shutil.copyfile(KML,D/'source-online.kml')
meta=json.loads((R/'web/metadata.json').read_text());lo=np.array(meta['features']['model_extent_utm47n'][:2]);hi=np.array(meta['features']['model_extent_utm47n'][2:]);scale=1000/meta['horizontal_scale'];tf=Transformer.from_crs(4326,32647,always_xy=True)
with rasterio.open(R/'data/terrain_crop.tif') as src:heights=src.read(1)[::-1];ny,nx=heights.shape
vertices=np.fromfile(R/'web/vertices.bin',dtype='<f4').reshape(-1,3)[:nx*ny].reshape(ny,nx,3)
ns={'k':'http://www.opengis.net/kml/2.2'}
online_root=ET.parse(KML).getroot()
def picture_points(root):
 result=[]
 for folder in root.findall('.//k:Folder',ns):
  if folder.findtext('k:name',default='',namespaces=ns)!='标注点':continue
  for pm in folder.findall('k:Placemark',ns):
   if pm.findtext('k:styleUrl',default='',namespaces=ns).lstrip('#')=='MarkerStylePicture':result.append(pm)
 return result
online={p.findtext("k:ExtendedData/k:Data[@name='FileId']/k:value",namespaces=ns):p for p in picture_points(online_root)}
points=[]
with zipfile.ZipFile(KMZ) as archive:
 raw=archive.read('doc.kml');(D/'doc.kml').write_bytes(raw);root=ET.fromstring(raw)
 pms=picture_points(root);assert len(pms)==28
 for index,pm in enumerate(pms,1):
  data={e.get('name'):e.findtext('k:value',default='',namespaces=ns) for e in pm.findall('k:ExtendedData/k:Data',ns)}
  fileid=data['FileId'];assert fileid.isdigit();member=f'files/pic_{fileid}.png'
  original=archive.read(member);(D/'originals'/f'pic_{fileid}.png').write_bytes(original)
  lon,lat,recorded=map(float,pm.findtext('k:Point/k:coordinates',namespaces=ns).split(','))
  assert abs(lon-float(data['Longtitude']))<1e-7 and abs(lat-float(data['Latitude']))<1e-7
  other=online[fileid];assert other.findtext('k:Point/k:coordinates',namespaces=ns)==pm.findtext('k:Point/k:coordinates',namespaces=ns)
  x,y=tf.transform(lon,lat);inside=bool(np.all(np.array([x,y])>=lo)&np.all(np.array([x,y])<=hi));model_xy=(np.array([x,y])-lo)*scale
  dem_elevation=None;dem_z=None;surface_z=None
  if inside:
   ix=(x-lo[0])/(hi[0]-lo[0])*(nx-1);iy=(y-lo[1])/(hi[1]-lo[1])*(ny-1)
   dem_elevation=float(map_coordinates(heights,[[iy],[ix]],order=1)[0]);dem_z=meta['base_mm']+(dem_elevation-meta['terrain_elevation_m'][0])*scale*meta['vertical_exaggeration']
   i=min(int(ix),nx-2);j=min(int(iy),ny-2);fx=ix-i;fy=iy-j
   a,b,c,d=vertices[j,i,2],vertices[j,i+1,2],vertices[j+1,i,2],vertices[j+1,i+1,2]
   surface_z=float((1-fx)*a+(fx-fy)*b+fy*d if fx>=fy else (1-fy)*a+fx*d+(fy-fx)*c)
  timestamp=int(data['Time']);localtime=datetime.fromtimestamp(timestamp/1000,tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
  with Image.open(io.BytesIO(original)) as im:
   fmt=im.format;size=im.size;clean=ImageOps.exif_transpose(im).convert('RGB');clean.thumbnail((1200,1200),Image.Resampling.LANCZOS);display_size=clean.size
   clean.save(W/f'{fileid}.jpg',quality=85,optimize=True,progressive=True)
   thumb=clean.copy();thumb.thumbnail((240,240),Image.Resampling.LANCZOS);thumb.save(W/'thumbs'/f'{fileid}.jpg',quality=78,optimize=True)
  points.append({'id':fileid,'index':index,'label':f'照片 {index:02d}','name':pm.findtext('k:name',default='',namespaces=ns),'note':data.get('description','') or '',
   'timestamp_ms':timestamp,'time_iso':localtime.isoformat(),'time_local':localtime.strftime('%Y-%m-%d %H:%M:%S'),'timezone':'Asia/Shanghai',
   'longitude':lon,'latitude':lat,'recorded_altitude_m':recorded,'dem_elevation_m':dem_elevation,
   'utm47n_m':[x,y],'in_model':inside,'out_of_bounds_reason':None if inside else 'Outside unchanged model rectangle',
   'model_position_mm':[float(model_xy[0]),float(model_xy[1]),dem_z],'rendered_surface_z_mm':surface_z,
   'marker_lift_mm':2.2,'image':f'./photos/{fileid}.jpg','thumbnail':f'./photos/thumbs/{fileid}.jpg',
   'archive_member':member,'original_file':f'data/photos-2026-01-27/originals/pic_{fileid}.png','original_sha256':hashlib.sha256(original).hexdigest(),
   'original_encoding':fmt,'original_dimensions':list(size),'web_dimensions':list(display_size)})
assert len({p['id'] for p in points})==28
summary={'hike_date':'2026-01-27','hike_label':'尼龙进村（2026-01-27）','base_route_date':'2026-09-17','same_hike_as_base_route':False,
 'total':len(points),'in_bounds':sum(p['in_model'] for p in points),'out_of_bounds':[{'id':p['id'],'index':p['index'],'longitude':p['longitude'],'latitude':p['latitude'],'reason':p['out_of_bounds_reason']} for p in points if not p['in_model']],
 'data_url':'./photos/points.json','source_archive':'data/photos-2026-01-27/source.kmz','source_online_kml':'data/photos-2026-01-27/source-online.kml',
 'source_hashes':source_hashes,'coordinate_crs':'WGS84 → EPSG:32647','elevation_source':'Bilinear sample of existing Copernicus DEM crop; recorded altitude not used for placement',
 'marker_placement':'Anchor at DEM elevation; UI-only stem/symbol raised above rendered relief to remain visible','time_source':'KML ExtendedData Time (milliseconds); not verified against photo EXIF capture time','rights':'User-provided photos; no open redistribution license inferred','print_geometry_unchanged':protected}
manifest={'summary':summary,'points':points};(D/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False));(W/'points.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
meta['photos']=summary
# User supplied external browser verification for the prior feature-only preview.
meta['browser_validation']={'status':'passed_external','screenshot_created':True,'screenshot':'web/preview-features.png','scope':'Feature-only version before photo overlay','evidence':'User reports external headless Chrome rendered normally and supplied screenshot','photo_overlay_validation':'not yet browser verified'}
(R/'web/metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False))
assert protected=={str(p.relative_to(R)):sha(p) for p in (R/'models').glob('*') if p.suffix in ('.stl','.3mf')}
assert source_hashes=={str(p):sha(p) for p in [KMZ,KML]}
print(json.dumps(summary,indent=2,ensure_ascii=False))
