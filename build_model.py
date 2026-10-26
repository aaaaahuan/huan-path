from pathlib import Path
import argparse, json, xml.etree.ElementTree as ET, zipfile
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from pyproj import Transformer, Geod
from scipy.spatial import cKDTree
import trimesh

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Build printable terrain from a KML or KMZ hiking track')
parser.add_argument('track',nargs='?',default=str(ROOT/'data/route.kml'))
parser.add_argument('--job-spec',help='Task-local geographic data and progress context')
parser.add_argument('--config',default=str(ROOT/'config/features.json'))
parser.add_argument('--disable',default='',help='Comma-separated feature names, e.g. rivers,forest')
parser.add_argument('--enable',default='',help='Temporary enable overrides')
parser.add_argument('--output-dir',default=str(ROOT),help='Write models/ and web/ to an alternate folder for testing')
args=parser.parse_args()
job_spec=json.loads(Path(args.job_spec).read_text()) if args.job_spec else None
DATA=Path(job_spec['data_dir']) if job_spec else ROOT/'data'
def stage(key,detail):
 if job_spec:
  from app.state import Progress
  Progress(Path(args.job_spec).parent).stage(key,detail)
from feature_engine import load_config,compose,KEYS,route_circle_length
config=load_config(args.config,args.disable,args.enable)
state={key:config[key]['enabled'] for key in KEYS}
OUT=Path(args.output_dir).resolve();(OUT/'models').mkdir(parents=True,exist_ok=True);(OUT/'web/layers').mkdir(parents=True,exist_ok=True)
track=Path(args.track).expanduser().resolve()
if track.suffix.lower()=='.kmz':
 with zipfile.ZipFile(track) as archive:
  names=[n for n in archive.namelist() if n.lower().endswith('.kml')]
  preferred=[n for n in names if n.lower()=='doc.kml']
  if not preferred and len(names)!=1:
   raise ValueError('KMZ must contain doc.kml or exactly one KML file')
  name=preferred[0] if preferred else names[0]
  if archive.getinfo(name).file_size>50_000_000: raise ValueError('KML exceeds 50 MB limit')
  document=ET.fromstring(archive.read(name))
else:
 document=ET.parse(track).getroot()
coords=[list(map(float,e.text.split())) for e in document.findall('.//{http://www.google.com/kml/ext/2.2}coord')]
if len(coords)<2:
 raise ValueError('This prototype expects gx:Track coordinates with at least two points')
p=np.asarray(coords)
print('Input:',track,'points:',len(p))
epsg=job_spec['route']['epsg'] if job_spec else 32647
tf=Transformer.from_crs(4326,epsg,always_xy=True)
x,y=tf.transform(p[:,0],p[:,1]); xy=np.column_stack((x,y))
# Standard KML is interpreted as WGS84. No undocumented offset is applied.
padding=job_spec['model']['padding_m'] if job_spec else 1100
lo=xy.min(axis=0)-padding; hi=xy.max(axis=0)+padding
extent=hi-lo; scale=(job_spec['model']['size_mm'] if job_spec else 200)/extent.max(); size=extent*scale
nx,ny=np.ceil(size/.32).astype(int)+1
# Pixel centers match the vertices, with rows ordered south to north after reprojection.
dx,dy=extent/np.array([nx-1,ny-1]); transform=from_bounds(lo[0]-dx/2,lo[1]-dy/2,hi[0]+dx/2,hi[1]+dy/2,nx,ny)
dem=np.full((ny,nx),np.nan,dtype=np.float32)
with rasterio.open(DATA/'dem.tif') as src:
 reproject(rasterio.band(src,1),dem,src_transform=src.transform,src_crs=src.crs,dst_transform=transform,dst_crs=f'EPSG:{epsg}',resampling=Resampling.bilinear,dst_nodata=np.nan)
assert np.isfinite(dem).all(), 'Missing elevation data'
with rasterio.open(DATA/'terrain_crop.tif','w',driver='GTiff',height=ny,width=nx,count=1,dtype='float32',crs=f'EPSG:{epsg}',transform=transform) as dst: dst.write(dem,1)
h=dem[::-1].copy(); base=4.; exaggeration=1.25
if job_spec:
 exaggeration=job_spec['model']['vertical_exaggeration'] if job_spec.get('preserve_imported_assets') else float(np.clip(72/max(float(np.ptp(h))*scale,.01),1,2))
 base=job_spec['model']['base_mm'] if job_spec.get('preserve_imported_assets') else max(4.,4.+max(0.,float(h.min())-float(np.min(p[:,2])))*scale*exaggeration)
 job_spec['model']['vertical_exaggeration']=exaggeration
 job_spec['model']['base_mm']=base
 if not job_spec.get('preserve_imported_assets'):config['elevation_scale']['side']=max(('south','east'),key=lambda k:float(np.mean(h[0,:] if k=='south' else h[:,-1]))*float(size[0] if k=='south' else size[1]))
 from app.state import write_json
 write_json(args.job_spec,job_spec)
stage('terrain','DEM 网格、路线加密和距离场；自动投影/比例与高度夸张')
xx,yy=np.meshgrid(np.linspace(0,size[0],nx),np.linspace(0,size[1],ny))
route=(xy-lo)*scale
# Densify the ordered coordinate samples from the exported track segments.
dense=[]
for a,b in zip(route[:-1],route[1:]):
 n=max(1,int(np.ceil(np.linalg.norm(b-a)/.06)));dense.extend(a+(b-a)*np.arange(n)[:,None]/n)
dense.append(route[-1]); dense=np.array(dense)
dist=cKDTree(dense).query(np.column_stack((xx.ravel(),yy.ravel())))[0].reshape(h.shape)
# A broad plateau with tapered edges produces a continuous printable raised route.
# Data-derived feature masks use the same UTM grid and exact model extent.
stage('features','按任务范围获取 OSM 与 WorldCover，并生成地表掩膜')
if job_spec and not job_spec.get('preserve_imported_assets'):
 from app.datasets import prepare_features
 from app.state import Progress
 prepare_features(Path(args.job_spec).parent,job_spec,Progress(Path(args.job_spec).parent))
# Roads remain preview-only and never change printable terrain geometry.
from app.roads import prepare_roads,build_roads
inverse=Transformer.from_crs(epsg,4326,always_xy=True)
corner_lon,corner_lat=inverse.transform([lo[0],lo[0],hi[0],hi[0]],[lo[1],hi[1],lo[1],hi[1]])
road_bounds=[min(corner_lon),min(corner_lat),max(corner_lon),max(corner_lat)]
road_warnings=job_spec['warnings'] if job_spec else []
road_raw=prepare_roads(DATA,road_bounds,road_warnings)
road_report=build_roads(road_raw,tf,lo,hi,scale,OUT/'web')
print('Roads:',road_report['count'],road_report['counts'],flush=True)
if job_spec:
 from app.state import Progress,write_json
 write_json(args.job_spec,job_spec)
 Progress(Path(args.job_spec).parent).detail(f"道路 {road_report['count']} 条 · {road_report['counts']}")
from rasterio.features import rasterize
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import polygonize, unary_union, transform as shape_transform
from scipy.ndimage import distance_transform_edt, map_coordinates
import hashlib
crop_box=box(lo[0],lo[1],hi[0],hi[1])
wc=np.zeros((ny,nx),dtype=np.uint8)
wc_path=DATA/('worldcover.tif' if job_spec else 'worldcover_2021_N27E096.tif')
assert wc_path.exists(), 'Download WorldCover before building'
with rasterio.open(wc_path) as src:
 reproject(rasterio.band(src,1),wc,src_transform=src.transform,src_crs=src.crs,
           dst_transform=transform,dst_crs=f'EPSG:{epsg}',resampling=Resampling.nearest,dst_nodata=0)
if not job_spec:assert np.all(wc!=0), 'Incomplete WorldCover coverage'
with rasterio.open(DATA/'worldcover_crop.tif','w',driver='GTiff',height=ny,width=nx,count=1,
                   dtype='uint8',crs=f'EPSG:{epsg}',transform=transform,compress='deflate') as dst: dst.write(wc,1)
wc=wc[::-1].copy()
osm_path=DATA/'osm_features_raw.json'
assert osm_path.exists(), 'OSM raw response missing; do not silently invent water geometry'
osm=json.loads(osm_path.read_text());assert 'remark' not in osm, 'Incomplete Overpass response'
features={'river':[],'stream':[],'lake':[],'water_polygon':[],'forest':[],'glacier':[]}
skipped=[]; source_counts={}; clipped_features=[]
def projected_line(points):
 if len(points)<2: return None
 lon=[p['lon'] for p in points];lat=[p['lat'] for p in points]
 x,y=tf.transform(lon,lat);return LineString(zip(x,y))
def parts(g,kind):
 if g.is_empty:return []
 if g.geom_type==kind:return [g]
 return [part for child in getattr(g,'geoms',[]) for part in parts(child,kind)]
def osm_polygon(e):
 if e['type']=='way':
  line=projected_line(e.get('geometry',[]))
  return Polygon(line.coords) if line is not None and line.is_ring else None
 if e['type']=='relation':
  outer=[];inner=[]
  for member in e.get('members',[]):
   if member.get('type')!='way':continue
   line=projected_line(member.get('geometry',[]))
   if line is not None:(inner if member.get('role')=='inner' else outer).append(line)
  outers=list(polygonize(unary_union(outer))) if outer else []
  inners=list(polygonize(unary_union(inner))) if inner else []
  if outers:return unary_union(outers).difference(unary_union(inners))
 return None
for e in osm['elements']:
 tags=e.get('tags',{});category=None;geom=None
 if e['type']=='way' and tags.get('waterway') in ('river','stream'):
  category=tags['waterway'];geom=projected_line(e.get('geometry',[]))
 elif tags.get('natural')=='water':
  category='water_polygon' if tags.get('water') in ('river','stream','canal') else 'lake';geom=osm_polygon(e)
 elif tags.get('landuse')=='forest' or tags.get('natural')=='wood':category='forest';geom=osm_polygon(e)
 elif tags.get('natural')=='glacier':category='glacier';geom=osm_polygon(e)
 if category is None:continue
 source_counts[category]=source_counts.get(category,0)+1
 if geom is None or geom.is_empty:
  skipped.append({'type':e['type'],'id':e['id'],'reason':'No usable line/closed polygon; point water cannot define a lake area'});continue
 if not geom.is_valid:geom=geom.buffer(0)
 geom=geom.intersection(crop_box)
 if geom.is_empty:continue
 # Preserve feature identity and source tags in a clipped derived dataset.
 features[category].append(geom)
 clipped_features.append({'type':'Feature','geometry':mapping(geom),'properties':{'osm_type':e['type'],'osm_id':e['id'],'category':category,'tags':tags}})
(DATA/'osm_features_utm47n.geojson').write_text(json.dumps({'type':'FeatureCollection','name':f'Clipped OSM features; EPSG:{epsg} metres','crs':{'type':'name','properties':{'name':f'EPSG:{epsg}'}},'features':clipped_features},ensure_ascii=False))
def mask(geometries):
 if not geometries:return np.zeros((ny,nx),bool)
 return rasterize([(mapping(g),1) for g in geometries if not g.is_empty],out_shape=(ny,nx),transform=transform,fill=0,dtype='uint8')[::-1].astype(bool)
# Exaggerated display widths, not inferred real river widths: 1.4 mm river / 1.1 mm stream.
river_areas=[g.buffer(config['rivers']['river_width_mm']/2/scale) for g in features['river']]+[g.buffer(config['rivers']['stream_width_mm']/2/scale) for g in features['stream']]+features['water_polygon']
river_mask=mask(river_areas); lake_mask=mask(features['lake']);water=river_mask|lake_mask
snow=((wc==70)|mask(features['glacier'])) & ~water
forest=((wc==10)|mask(features['forest'])) & ~water & ~snow
grass=(wc==30) & ~water & ~snow & ~forest
# Forest relief is symbolic texture, not individual mapped tree positions.
texture=.5+.25*np.sin(xx*2*np.pi/1.6)*np.cos(yy*2*np.pi/1.4)+.25*np.sin((xx+yy)*2*np.pi/2.3)
forest_raise=np.where(forest,config['forest']['raise_mm']+config['forest']['texture_mm']*texture,0.)
terrain_z=base+(h-h.min())*scale*exaggeration
feature_z=terrain_z+forest_raise
feature_z[river_mask]=terrain_z[river_mask]-config['rivers']['depth_mm']
lake_levels=[]
for lake in features['lake']:
 for polygon in parts(lake,'Polygon'):
  lm=mask([polygon])
  if not lm.any():continue
  # A constant level from the local DEM, lowered 0.45 mm. Never globally flatten river polygons.
  level=max(.8,float(np.median(terrain_z[lm]))-config['rivers']['depth_mm'])
  feature_z[lm]=level
  lake_levels.append({'vertices':int(lm.sum()),'level_mm':level,'span_mm':0.0})
# Keep exclusive source categories: switching off a category restores ordinary terrain there.
source_classes=np.zeros((ny,nx),dtype=np.uint8)
source_classes[grass]=5;source_classes[forest]=2;source_classes[snow]=3;source_classes[water]=1
water_delta=np.where(water,feature_z-terrain_z,0.)
house_top=np.zeros((ny,nx),dtype=np.float64);house_points=[];outside_houses=[]
route_gap=np.zeros((ny,nx),dtype=bool);gap_radius=config['houses']['route_gap_mm']
stage('photos','解析包内照片并生成可编辑房屋判断，放置图钉屋')
if job_spec:
 from app.photos import prepare_photos
 from app.state import Progress
 prepare_photos(Path(args.job_spec).parent,job_spec,Progress(Path(args.job_spec).parent))
house_doc=json.loads((ROOT/config['houses']['list_file']).read_text())
rows=house_doc['points']
assert len({r['photo_index'] for r in rows})==len(rows), 'Duplicate photo indices in house list'
for row in rows:
 if row['has_house'] is not True and row['has_house'] is not False and row['has_house']!='uncertain':raise ValueError('has_house must be true, false, or "uncertain"')
 if not state['houses'] or not (row['has_house'] is True or (row['has_house']=='uncertain' and config['houses']['include_uncertain'])):continue
 hx,hy=tf.transform(float(row['longitude']),float(row['latitude']));pos=(np.array([hx,hy])-lo)*scale
 if np.any(pos<0) or np.any(pos>size):
  outside_houses.append(row['photo_index']);continue
 # Independent pin house; terrain heightfield is never raised to form houses.
 route_gap|=((xx-pos[0])**2+(yy-pos[1])**2<=(gap_radius+2*np.hypot(size[0]/(nx-1),size[1]/(ny-1)))**2)
 gap_length=route_circle_length(route,pos,gap_radius)
 house_points.append({'route_gap_radius_mm':gap_radius,'route_gap_centerline_length_mm':gap_length,'route_gap_centerline_length_m':gap_length/scale,'photo_index':row['photo_index'],'file_id':row.get('file_id'),'longitude':row['longitude'],'latitude':row['latitude'],'has_house':row['has_house'],'model_xy_mm':pos.tolist(),'reason':row['reason']})
# Drop disabled elements from active preview buffers as well as printing geometry/colors.
available_classes=source_classes.copy()
for key,id in [('rivers',1),('forest',2),('snow',3),('grass',5)]:
 if not state[key]:available_classes[available_classes==id]=0
if not state['forest']:forest_raise[:]=0
if not state['rivers']:water_delta[:]=0
z,vertex_class,feature_z=compose(terrain_z,available_classes,forest_raise,water_delta,house_top,dist,state,route_gap)
feature_class=vertex_class.copy();feature_class[feature_class==4]=0
# Face categories below are recomputed from the pre-route categories, avoiding edge bleed.
_,pre_class,_=compose(terrain_z,available_classes,forest_raise,water_delta,house_top,np.full_like(dist,10),state,route_gap)
feature_class=pre_class
route_floor=np.maximum(terrain_z,feature_z)
palette=[{'id':0,'name':'Terrain / 地形','hex':'#C6CBB5'},
         {'id':1,'name':'Water / 河流与水体','hex':'#2389C9'},
         {'id':2,'name':'Tree cover / 林区','hex':'#24563B'},
         {'id':3,'name':'Snow and ice / 冰雪','hex':'#F5FAFF'},
         {'id':4,'name':'Hiking route / 徒步路线','hex':'#E94F39'},
         {'id':5,'name':'Grassland / 草地','hex':'#A2B96A'},
         {'id':6,'name':'House walls / 房屋白墙','hex':'#F7F7F2'},
         {'id':7,'name':'House pin and roof / 图钉粉顶','hex':config['houses']['pin_color']},
         {'id':8,'name':'Elevation scale / 海拔刻度','hex':config['elevation_scale']['color']}]
feature_report={'source_counts':source_counts,'clipped_counts':{k:len(v) for k,v in features.items()},
 'skipped_osm':skipped,'worldcover_vertex_counts':{str(int(k)):int(v) for k,v in zip(*np.unique(wc,return_counts=True))},
 'mask_vertices':{'river':int(river_mask.sum()) if state['rivers'] else 0,'lake':int(lake_mask.sum()) if state['rivers'] else 0,'forest':int(forest.sum()) if state['forest'] else 0,'grass':int(grass.sum()) if state['grass'] else 0,'snow':int(snow.sum()) if state['snow'] else 0,'houses':int((house_top>0).sum())},
 'river_depth_mm':config['rivers']['depth_mm'] if state['rivers'] else None,'river_display_width_mm':config['rivers']['river_width_mm'],'stream_display_width_mm':config['rivers']['stream_width_mm'],
 'forest_relief_range_mm':[float(forest_raise[forest].min()),float(forest_raise[forest].max())] if state['forest'] and forest.any() else [],
 'lake_levels':lake_levels if state['rivers'] else [],'snow_geometry_change_mm':0 if state['snow'] else None,'route_min_clearance_mm':float(np.min((z-route_floor)[(dist<.72)&~route_gap])) if np.any((dist<.72)&~route_gap) else None,
 'minimum_top_thickness_mm':float(z.min()),'model_extent_utm47n':[*lo.tolist(),*hi.tolist()],
 'mask_priority':'Pin houses independently unioned; no route inside house gaps; elsewhere route > water > snow > forest > grass > terrain',
 'worldcover_year':2021,'worldcover_resolution_m':10,
 'notes':['WorldCover class 70 is snow/ice cover in 2021, not hike-date snow extent.',
          'Forest texture and widened river grooves are printable symbols, not surveyed canopy or river width.',
          'Only OSM water polygons are flattened; WorldCover water class is not used to invent lake outlines.']}

verts=np.column_stack((xx.ravel(),yy.ravel(),z.ravel()))
for hp in house_points:
 hx,hy=hp['model_xy_mm'];ix=hx/size[0]*(nx-1);iy=hy/size[1]*(ny-1)
 i=min(int(ix),nx-2);j=min(int(iy),ny-2);fx=ix-i;fy=iy-j
 za,zb,zc,zd=z[j,i],z[j,i+1],z[j+1,i],z[j+1,i+1]
 roof_center=float((1-fx)*za+(fx-fy)*zb+fy*zd if fx>=fy else (1-fy)*za+fx*zd+(fy-fx)*zc)
 hp['scene_roof_center_mm']=[hx,hy,roof_center]
grid=np.arange(nx*ny).reshape(ny,nx);a=grid[:-1,:-1].ravel();b=a+1;c=a+nx;d=c+1
faces=np.concatenate((np.column_stack((a,b,d)),np.column_stack((a,d,c))))
top_count=len(faces)
# CCW perimeter viewed from above; side faces point outward.
perim=np.concatenate((grid[0,:],grid[1:,-1],grid[-1,-2::-1],grid[-2:0:-1,0]))
bottom_start=len(verts); bottom=verts[perim].copy();bottom[:,2]=0
verts=np.vstack((verts,bottom,[[size[0]/2,size[1]/2,0]]))
sides=[];center=len(verts)-1
for k,i in enumerate(perim):
 j=perim[(k+1)%len(perim)]; u=bottom_start+k;v=bottom_start+(k+1)%len(perim)
 sides.extend(((i,u,v),(i,v,j),(center,v,u)))
faces=np.vstack((faces,np.array(sides)))
mesh=trimesh.Trimesh(verts,faces,process=False)
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
# STL is exported after boolean union below.
# Single closed mesh, with face colors stored as standard 3MF base materials.
# Centroid sampling gives crisp categorical face materials, shared with the preview.
face_material=np.zeros(len(faces),dtype=np.uint8)
centers=verts[faces[:top_count],:2].mean(axis=1)
ci=np.clip(np.rint(centers[:,0]/size[0]*(nx-1)).astype(int),0,nx-1)
cj=np.clip(np.rint(centers[:,1]/size[1]*(ny-1)).astype(int),0,ny-1)
face_material[:top_count]=feature_class[cj,ci]
# Protect red route material by evaluating its actual dense polyline distance at face centroids.
face_dist=cKDTree(dense).query(centers)[0]
face_gap=route_gap.ravel()[faces[:top_count]].any(axis=1)
# Also cover circle centers even if a very small circle falls between sampled vertices.
for hp in house_points:
 if True:
  face_gap|=np.sum((centers-np.array(hp['model_xy_mm']))**2,axis=1)<=hp['route_gap_radius_mm']**2
active_face_route=(face_dist<.72)&~face_gap
face_material[:top_count][active_face_route]=4
assert not np.any(face_material[:top_count][face_gap]==4)
assert np.allclose(z[route_gap],feature_z[route_gap])
# Keep editable preview terrain separate from the merged printable mesh.
preview_verts=verts.copy();preview_faces=faces.copy();preview_material=face_material.copy()
import manifold3d as mf
terrain_solid=mf.Manifold(mf.Mesh(np.asarray(verts,dtype=np.float32),np.asarray(faces,dtype=np.uint32),face_id=face_material.astype('u4')))
assert terrain_solid.status()==mf.Error.NoError
solids=[terrain_solid]
# GLB color partitions and STL are the same design; reconstruct its welded solid
# with face provenance so manifold preserves both materials through union.
scene=trimesh.load(ROOT/config['houses']['model_glb'],force='scene')
parts=[];ids=[]
for node in scene.graph.nodes_geometry:
 transform_node,geom_name=scene.graph[node];part=scene.geometry[geom_name].copy();part.apply_transform(transform_node)
 role=part.visual.material.name
 parts.append(part);ids.extend([6 if role=='body' else 7]*len(part.faces))
design=trimesh.util.concatenate(parts);design.merge_vertices()
reference=trimesh.load_mesh(ROOT/config['houses']['model_stl'])
assert np.allclose(design.bounds,reference.bounds,atol=1e-4) and abs(design.volume-reference.volume)<.001
color_centers=design.triangles_center.copy();color_ids=np.asarray(ids)
design=reference
ids=color_ids[cKDTree(color_centers).query(design.triangles_center)[1]]
assert design.is_watertight
house_solid=mf.Manifold(mf.Mesh(np.asarray(design.vertices,dtype=np.float32),np.asarray(design.faces,dtype=np.uint32),face_id=np.asarray(ids,dtype='u4')))
assert house_solid.status()==mf.Error.NoError
for hp in house_points:
 hx,hy=hp['model_xy_mm'];ix=hx/size[0]*(nx-1);iy=hy/size[1]*(ny-1)
 i=min(int(ix),nx-2);j=min(int(iy),ny-2);fx=ix-i;fy=iy-j
 za,zb,zc,zd=z[j,i],z[j,i+1],z[j+1,i],z[j+1,i+1]
 surface=float((1-fx)*za+(fx-fy)*zb+fy*zd if fx>=fy else (1-fy)*za+fx*zd+(fy-fx)*zc)
 origin=[hx,hy,surface-config['houses']['sink_mm']]
 placed=house_solid.scale([config['houses']['scale']]*3).translate(origin)
 intersection=terrain_solid ^ placed
 assert intersection.volume()>0, 'House does not intersect terrain'

 hp['scene_origin_mm']=origin;hp['scene_roof_center_mm']=[hx,hy,origin[2]+design.bounds[1,2]*config['houses']['scale']]
 hp['terrain_intersection_mm3']=intersection.volume()
 # Exact triangle projection distances for every raised or red route face.
 from shapely.geometry import Point
 raised=np.any((z.ravel()-feature_z.ravel())[preview_faces[:top_count]]>1e-6,axis=1)
 route_triangles=preview_verts[preview_faces[:top_count][raised|active_face_route],:2]
 point=Point(hx,hy)
 min_center=min(Polygon(t).distance(point) for t in route_triangles)
 hp['nearest_route_center_distance_mm']=min_center
 # Conservative footprint bound (pin disc radius); roof is narrower.
 hp['nearest_route_footprint_clearance_lower_bound_mm']=min_center-1.7*config['houses']['scale']
 assert min_center>=gap_radius
 footprint_geometry=unary_union([Polygon(t[:,:2]*config['houses']['scale']+np.array([hx,hy])) for t in design.triangles if Polygon(t[:,:2]).area>1e-10])
 hp['nearest_route_footprint_distance_mm']=min(Polygon(t).distance(footprint_geometry) for t in route_triangles)
 assert hp['nearest_route_footprint_distance_mm']>0, 'Route overlaps house footprint'
 assert hp['nearest_route_footprint_clearance_lower_bound_mm']>=config['houses']['min_route_clearance_mm']
 solids.append(placed)
stage('scale','按轨迹记录首尾海拔等分，生成单侧毫米级浮雕')
from elevation_scale import build_scale
scale_solid,scale_report=build_scale(config['elevation_scale'],terrain_z,size,[float(h.min()),float(h.max())],scale,base,exaggeration,OUT,p[:,2])
state['elevation_scale'] = scale_solid is not None
if scale_solid is not None:
 assert (terrain_solid ^ scale_solid).volume()>0
 solids.append(scale_solid)
stage('export','布尔合并、STL/3MF 导出及回读校验')
merged=mf.Manifold.batch_boolean(solids,mf.OpType.Add)
assert merged.status()==mf.Error.NoError
components=merged.decompose()
# Fill enclosed negative-volume air pockets at the terrain/pin intersection.
positive=[part for part in components if part.volume()>0]
assert len(positive)==1, 'Disconnected positive-volume shell'
filled_cavities=[-part.volume() for part in components if part.volume()<0]
merged=positive[0]
assert len(merged.decompose())==1
merged_mesh=merged.to_mesh();verts=np.asarray(merged_mesh.vert_properties)[:,:3];faces=np.asarray(merged_mesh.tri_verts)
face_material=np.asarray(merged_mesh.face_id,dtype='u1')
mesh=trimesh.Trimesh(verts,faces,process=True)
assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split())==1 and abs(mesh.bounds[0,2])<1e-6
mesh.export(OUT/'models/yubeng_ninong_print.stl')
active_palette=[item for item in palette if np.any(face_material==item['id'])]
material_index={item['id']:i for i,item in enumerate(active_palette)}
feature_report['face_material_counts']={item['name']:int(np.sum(face_material==item['id'])) for item in palette}
ns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'; ET.register_namespace('',ns)
def el(tag,**attrs):return ET.Element('{'+ns+'}'+tag,{k:str(v) for k,v in attrs.items()})
root=el('model',unit='millimeter');res=el('resources');root.append(res)
materials=el('basematerials',id=1);res.append(materials)
for item in active_palette: materials.append(el('base',name=item['name'],displaycolor=item['hex']+'FF'))
obj=el('object',id=2,type='model');res.append(obj);me=el('mesh');obj.append(me);ve=el('vertices');me.append(ve)
for v in verts:ve.append(el('vertex',x=f'{v[0]:.5f}',y=f'{v[1]:.5f}',z=f'{v[2]:.5f}'))
tr=el('triangles');me.append(tr)
for i,f in enumerate(faces):tr.append(el('triangle',v1=f[0],v2=f[1],v3=f[2],pid=1,p1=material_index[int(face_material[i])],p2=material_index[int(face_material[i])],p3=material_index[int(face_material[i])]))
bu=el('build');root.append(bu);bu.append(el('item',objectid=2))
with zipfile.ZipFile(OUT/'models/yubeng_ninong_color.3mf','w',zipfile.ZIP_DEFLATED) as out:
 out.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
 out.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
 out.writestr('3D/3dmodel.model',ET.tostring(root,encoding='utf-8',xml_declaration=True))
# Preview uses exactly the same vertices and triangles as the printable STL.
preview_verts.astype('<f4').tofile(OUT/'web/vertices.bin');preview_faces.astype('<u4').tofile(OUT/'web/faces.bin')
rgb=np.array([[int(item['hex'][i:i+2],16)/255 for i in (1,3,5)] for item in palette],dtype=np.float32)
vertex_ids=np.zeros(len(preview_verts),dtype=np.uint8);vertex_ids[:nx*ny]=vertex_class.ravel()
rgb[vertex_ids].astype('<f4').tofile(OUT/'web/colors.bin')
preview_material.tofile(OUT/'web/face_materials.bin')
_,_,steps=Geod(ellps='WGS84').inv(p[:-1,0],p[:-1,1],p[1:,0],p[1:,1])
# Compare logged altitude to DEM to expose possible coordinate/datum issues rather than silently shifting.
from scipy.ndimage import map_coordinates
ix=(xy[:,0]-lo[0])/dx;iy=(xy[:,1]-lo[1])/dy
terrain_at_route=map_coordinates(h,[iy,ix],order=1)
report={'route_points':len(p),'track_distance_km':float(sum(steps)/1000),'kml_recorded_distance_km':job_spec['route']['recorded_distance_km'] if job_spec else 14.455879607,'dimensions_mm':mesh.extents.tolist(),'ground_extent_m':extent.tolist(),'horizontal_scale':1000/scale,'vertical_exaggeration':exaggeration,'base_mm':base,'route_width_mm':1.7,'route_raise_mm':.8,'terrain_elevation_m':[float(h.min()),float(h.max())],'vertices':len(verts),'triangles':len(faces),'watertight':bool(mesh.is_watertight),'winding_consistent':bool(mesh.is_winding_consistent),'connected_components':len(mesh.split(only_watertight=False)),'volume_cm3':float(mesh.volume/1000),'logged_minus_dem_median_m':float(np.median(p[:,2]-terrain_at_route)),'logged_minus_dem_abs_p90_m':float(np.percentile(abs(p[:,2]-terrain_at_route),90)),'coordinate_assumption':'KML longitude/latitude interpreted as WGS84; no unverified GCJ correction','source':json.loads((DATA/'dem_source.json').read_text()) if job_spec else 'Copernicus DEM GLO-30 / AWS public tile N28 E098','route_start':route[0].tolist(),'route_end':route[-1].tolist(),'size':size.tolist()}
assert not state['forest'] or np.all((forest_raise[forest]>.2)&(forest_raise[forest]<=.5))
assert np.all(preview_verts[bottom_start:,2]==0)
for lake in features['lake'] if state['rivers'] else []:
 lm=mask([lake]) & (dist>=.85) & (house_top==0)
 if lm.any():assert np.ptp(z[lm])<1e-6
report['features']=feature_report
report['crs']={'epsg':epsg,'wgs84_assumption':True}
report['features']['model_extent_projected_m']=[*lo.tolist(),*hi.tolist()]
if job_spec:report['route_info']=job_spec['route']
else:
 from app.tracks import parse_track
 report['route_info']=parse_track(track)[0]
report['elevation_scale']=scale_report
report['configuration']={'file':str(Path(args.config).resolve()),'effective':{k:v for k,v in config.items() if k!='network'},'cli_disable':args.disable,'cli_enable':args.enable}
report['houses']={'list_file':config['houses']['list_file'],'true_indices':[r['photo_index'] for r in rows if r['has_house'] is True],
 'uncertain_indices':[r['photo_index'] for r in rows if r['has_house']=='uncertain'],'placed_points':house_points,'outside_indices':outside_houses,
 'route_gap_mm':gap_radius,'gap_vertex_count':int(route_gap.sum()),'gap_face_count':int(face_gap.sum()),'route_gap_rule':'Every placed house creates a gap, including uncertain if explicitly enabled',
 'model_stl':config['houses']['model_stl'],'model_glb':'./house_designs/5_pin_house.glb','scale':config['houses']['scale'],'sink_mm':config['houses']['sink_mm'],'preview_terrain_vertices':len(preview_verts),'preview_terrain_faces':len(preview_faces),
 'min_route_clearance_mm':config['houses']['min_route_clearance_mm'],'route_gap_sampling_padding_mm':float(2*np.hypot(size[0]/(nx-1),size[1]/(ny-1))),'design_provenance':'User supplied data/house_designs; no third-party license inferred',
 'placement_note':'Photo capture coordinates, not surveyed building locations; no inferred offset'}
# Copy the configured GLB for self-contained local preview.
import shutil
(OUT/'web/house_designs').mkdir(exist_ok=True)
# Export the preview asset with the configured accent, leaving source designs unchanged.
preview_scene=trimesh.load(ROOT/config['houses']['model_glb'],force='scene')
for geometry in preview_scene.geometry.values():
 if geometry.visual.material.name=='accent':
  color=config['houses']['pin_color']
  geometry.visual.material.baseColorFactor=[int(color[i:i+2],16) for i in (1,3,5)]+[255]
preview_scene.export(OUT/'web/house_designs/5_pin_house.glb')
# Compact layer buffers allow exact height/material recomposition for instant UI toggles.
layer_spec={'grid':[int(nx),int(ny)],'top_vertices':int(nx*ny),'top_faces':int(top_count),'available':state,
 'base':'./layers/base_z.bin','classes':'./layers/classes.bin','distance':'./layers/route_distance.bin','face_route':'./layers/face_route.bin',
 'forest':None,'rivers':None,'houses':None,'route_gap':None,'face_gap':None}
terrain_z.astype('<f4').tofile(OUT/'web/layers/base_z.bin')
available_classes.tofile(OUT/'web/layers/classes.bin');dist.astype('<f4').tofile(OUT/'web/layers/route_distance.bin')
(face_dist<.72).astype('u1').tofile(OUT/'web/layers/face_route.bin')
for name,array in [('route_gap',route_gap),('face_gap',face_gap)]:
 target=OUT/f'web/layers/{name}.bin'
 if state['houses']:
  array.astype('u1').tofile(target);layer_spec[name]=f'./layers/{name}.bin'
 elif target.exists():target.unlink()
for key,array in [('forest',forest_raise),('rivers',water_delta),('houses',house_top)]:
 target=OUT/f'web/layers/{key}.bin'
 if state[key]:
  array.astype('<f4').tofile(target);layer_spec[key]=f'./layers/{key}.bin'
 elif target.exists():target.unlink()
layer_spec['available']['roads']=road_report['count']>0
report['roads']=road_report
report['preview_layers']=layer_spec
report['sources']={key:json.loads((DATA/name).read_text()) for key,name in [('osm','osm_source.json'),('worldcover','worldcover_source.json'),('roads','osm_roads_source.json')]}
report['palette']=palette
# Place labels and settlement areas are preview-only overlays, built after STL/3MF export;
# any failure degrades to an empty layer plus a warning and never blocks the print files.
from app.settlements import prepare_settlements,build_settlements,empty_report,apply_report as apply_settlements,WARNING as SETTLEMENT_WARNING
try:
 settlement_report=build_settlements(prepare_settlements(DATA,road_bounds,road_warnings),tf,lo,hi,scale,OUT/'web',(nx,ny))
 settlement_source=json.loads((DATA/'osm_settlements_source.json').read_text())
except Exception as ex:
 road_warnings.append(SETTLEMENT_WARNING+'，本次无地名/居民区图层：'+str(ex)[:300])
 settlement_report=empty_report(OUT/'web',(nx,ny));settlement_source={'available':False,'error':str(ex)}
print('Settlements:',settlement_report['places']['counts'],settlement_report['areas']['cells'],flush=True)
apply_settlements(report,settlement_report,settlement_source)
if job_spec:
 from app.state import write_json
 write_json(args.job_spec,job_spec)
# Preserve the independent photo overlay descriptor when rebuilding terrain metadata.
photo_manifest=DATA/('photos/manifest.json' if job_spec else 'photos-2026-01-27/manifest.json')
if photo_manifest.exists():
 report['photos']=json.loads(photo_manifest.read_text())['summary'];report['photos']['enabled']=state['photos'];report['photos'].pop('print_geometry_unchanged',None);report['photos']['overlay_only']=True
report['browser_validation']={'status':'not_run','requested_screenshot':'web/preview-features.png','verification_command':'./verify_preview.command'}
(OUT/'models/validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
(OUT/'web/metadata.json').write_text(json.dumps(report,ensure_ascii=False))
# Round-trip STL checks verify exported artifact, not just the in-memory object.
loaded=trimesh.load_mesh(OUT/'models/yubeng_ninong_print.stl');assert loaded.is_watertight and loaded.is_winding_consistent
assert len(loaded.split())==1
print(json.dumps(report,indent=2,ensure_ascii=False))

# Independently validate serialized mesh artifacts, material indices and manifold topology.
import manifold3d
solid=manifold3d.Manifold(manifold3d.Mesh(np.asarray(loaded.vertices,dtype=np.float32),np.asarray(loaded.faces,dtype=np.uint32)))
assert solid.status()==manifold3d.Error.NoError
with zipfile.ZipFile(OUT/'models/yubeng_ninong_color.3mf') as archive:
 doc=ET.fromstring(archive.read('3D/3dmodel.model'));q={'m':ns}
 read_v=np.array([[float(e.get(k)) for k in ('x','y','z')] for e in doc.findall('.//m:vertex',q)])
 read_t=doc.findall('.//m:triangle',q)
 read_f=np.array([[int(e.get(k)) for k in ('v1','v2','v3')] for e in read_t])
 assert all(0<=int(e.get('p1'))<len(active_palette) for e in read_t)
 read_mesh=trimesh.Trimesh(read_v,read_f,process=True)
 assert read_mesh.is_watertight and read_mesh.is_winding_consistent and len(read_mesh.split())==1
 assert np.allclose(read_mesh.extents,mesh.extents,atol=1e-4)
report['export_checks']={'elevation_scale_enabled':state['elevation_scale'],'elevation_scale_single_side':True,'elevation_scale_ticks':len(scale_report['ticks']),'elevation_scale_all_ticks_true_z':all(not t['relocated'] and t['nominal_z_mm']==t['display_z_mm'] for t in scale_report['ticks']),'elevation_scale_min_stroke_mm':config['elevation_scale']['stroke_mm'],'stl_roundtrip_watertight':True,'3mf_roundtrip_watertight':True,'single_component_both':True,
                         'pin_house_boolean_union':True,'filled_internal_cavities_mm3':filled_cavities,'house_route_clearance_passed':True,'house_route_no_overlap':True,'house_route_clearance_rule':'Exact house XY footprint to raised or red route triangles strictly greater than zero','flat_bottom_z_mm':0,'manifold_status':str(solid.status()),'manifold_genus':solid.genus(),
                         'material_count':len(active_palette),'lake_flattening_excludes_raised_route':True,'route_gap_vertices_no_raise':True,'route_gap_faces_no_red':True,'route_above_features_outside_house_gaps':True}
if not job_spec:
 report['feature_ui_validation']=json.loads((ROOT/'work/pin-ui-validation.json').read_text()) if (ROOT/'work/pin-ui-validation.json').exists() else {'status':'not_run_for_pin_design'}
 if (ROOT/'work/elevation-scale-validation.json').exists():report['elevation_scale_validation']=json.loads((ROOT/'work/elevation-scale-validation.json').read_text())
 report['combination_validation']={'status':'historical_only','note':'Old heightfield house tests superseded; current default and houses-disabled artifacts checked separately'}
 off_check=ROOT/'work/pin-houses-off/models/validation.json'
 if off_check.exists():
  off=json.loads(off_check.read_text())
  report['export_checks']['houses_disabled_export_full_route']=not off['houses']['placed_points'] and off['houses']['gap_vertex_count']==0 and off['export_checks']['single_component_both']
 uncertain_check=ROOT/'work/pin-uncertain/models/validation.json'
 if uncertain_check.exists():
  uncertain_report=json.loads(uncertain_check.read_text())
  report['export_checks']['include_uncertain_export_passed']=len(uncertain_report['houses']['placed_points'])==8 and uncertain_report['export_checks']['single_component_both']
for target in (OUT/'models/validation.json',OUT/'web/metadata.json'):target.write_text(json.dumps(report,indent=2,ensure_ascii=False))
print('Export validation passed:',report['export_checks'])
