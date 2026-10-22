"""Printable side-wall elevation labels using a deterministic stroke font."""
import numpy as np
import manifold3d as mf

def build_scale(cfg,base_grid,size,dem_range,scale,base,exaggeration,out,route_elevations):
 side=cfg['side'];profiles={'south':base_grid[0,:],'north':base_grid[-1,::-1],'east':base_grid[:,-1],'west':base_grid[::-1,0]}
 stats={k:{'area_mm2':float(np.trapezoid(v,dx=float(size[0 if k in ('north','south') else 1])/(len(v)-1))),'max_z_mm':float(v.max())} for k,v in profiles.items()}
 source=cfg['source'];endpoints=dem_range if source=='terrain_min_max' else [float(route_elevations[0]),float(route_elevations[-1])]
 report={'source':source,'source_endpoints_m':list(endpoints),'dem_mapping_range_m':list(dem_range),'route_recorded_min_max_m':[float(np.min(route_elevations)),float(np.max(route_elevations))],'enabled':cfg['enabled'],'side':side,'side_statistics':stats,'ticks':[],'mode':'emboss','color':cfg['color'],'material_id':8,'preview_vertices':'./layers/elevation_scale_vertices.bin','preview_faces':'./layers/elevation_scale_faces.bin'}
 if not cfg['enabled']:
  for file in ('elevation_scale_vertices.bin','elevation_scale_faces.bin'):
   target=out/'web/layers'/file
   if target.exists():target.unlink()
  return None,report
 depth=cfg['depth_mm'];embed=.15;h=cfg['text_height_mm'];w=h*.54;t=cfg['stroke_mm'];space=t*.8
 def transform(solid):
  # Local (u,z,depth) -> world (x,y,z), text reads left to right from outside.
  if side=='south':mat=[[1,0,0,0],[0,0,1,-depth],[0,1,0,0]]
  elif side=='north':mat=[[-1,0,0,size[0]],[0,0,-1,size[1]+depth],[0,1,0,0]]
  elif side=='east':mat=[[0,0,-1,size[0]+depth],[1,0,0,0],[0,1,0,0]]
  else:mat=[[0,0,1,-depth],[-1,0,0,size[1]],[0,1,0,0]]
  return solid.transform(mat)
 def box(x,z,width,height):return mf.Manifold.cube([width,height,depth+embed]).translate([x,z,0])
 digits={'0':'abcedf','1':'bc','2':'abged','3':'abgcd','4':'fgbc','5':'afgcd','6':'afgecd','7':'abc','8':'abcdefg','9':'abfgcd'}
 def glyph(ch,x,z):
  seg={'a':(0,h-t,w,t),'g':(0,(h-t)/2,w,t),'d':(0,0,w,t),'f':(0,h/2,t,h/2),'b':(w-t,h/2,t,h/2),'e':(0,0,t,h/2),'c':(w-t,0,t,h/2)}
  if ch in ('S','E'):return [box(x+a,z+b,c,d) for k in ('afgcd' if ch=='S' else 'afged') for a,b,c,d in [seg[k]]]
  if ch.isdigit():return [box(x+a,z+b,c,d) for k in digits[ch] for a,b,c,d in [seg[k]]]
  if ch=='m':return [box(x,z,t,h*.75),box(x+w/2-t/2,z,t,h*.75),box(x+w-t,z,t,h*.75),box(x,z+h*.75-t,w,t)]
  if ch=='*':return [box(x,z+h*.4,w,t),box(x+w/2-t/2,z+h*.2,t,h*.6)]
  return []
 tick=cfg['line_width_mm'];line_len=cfg['tick_length_mm'];gap=1.5
 def try_layout(intervals,side_name):
  local_profile=profiles[side_name]-.6 # reserve headroom below boundary features
  local_length=float(size[0 if side_name in ('north','south') else 1])
  local_u=np.linspace(0,local_length,len(local_profile))
  pieces=[];occupied=[];ticks=[]
  for i,alt in enumerate(np.linspace(endpoints[0],endpoints[1],intervals+1)):
   nominal=float(base+(alt-dem_range[0])*scale*exaggeration)
   role='start' if i==0 else 'end' if i==intervals else 'intermediate'
   prefix=('S ' if role=='start' else 'E ' if role=='end' else '') if source=='route_start_end' else ''
   label=prefix+f'{alt:.0f} m';total=line_len+gap+len(label)*(w+space)
   starts=np.arange(3,local_length-total-3,.25)
   def ceiling(x,width):
    samples=np.r_[x,x+width,local_u[(local_u>x)&(local_u<x+width)]]
    return float(np.interp(samples,local_u,local_profile).min())
   ceilings=np.array([ceiling(x,total) for x in starts]);required=nominal+h/2+.6
   def free(x,z,width):return all(abs(z-z0)>=h+1 or x>=x0+w0+1 or x+width<=x0-1 for x0,z0,w0 in occupied)
   valid=np.array([j for j in np.flatnonzero(ceilings>=required) if free(float(starts[j]),nominal,total)],dtype=int)
   moved=not len(valid)
   if moved:
    label2=label+'*';total2=total+w+space;starts2=np.arange(3,local_length-total2-3,.25)
    ceilings2=np.array([ceiling(x,total2) for x in starts2])
    positions=[(min(nominal,float(top-h/2-.6)),float(x)) for x,top in zip(starts2,ceilings2) if min(nominal,float(top-h/2-.6))>h/2+1 and free(float(x),min(nominal,float(top-h/2-.6)),total2)]
    if not positions:return None
    display,x=max(positions,key=lambda v:(v[0],-v[1]));label=label2;total=total2
   else:x=float(starts[valid[0]]);display=nominal
   if not (display-h/2>1 and display>0):return None
   occupied.append((x,display,total))
   pieces.append(box(x,display-tick/2,line_len,tick))
   for j,ch in enumerate(label):pieces.extend(glyph(ch,x+line_len+gap+j*(w+space),display-h/2))
   ticks.append({'role':role,'elevation_m':float(alt),'label':label,'nominal_z_mm':nominal,'display_z_mm':display,'relocated':moved,'local_u_mm':x})
  return pieces,ticks,side_name,intervals
 # Try configured side first, then remaining south → east → north → west; reduce ticks per side.
 preferred=cfg['intervals'];sides=[side]+[s for s in ('south','east','north','west') if s!=side]
 layout=None;attempts=[]
 for candidate_side in sides:
  for intervals in list(range(preferred,0,-1)):
   result=try_layout(intervals,candidate_side)
   attempts.append({'side':candidate_side,'intervals':intervals,'ok':result is not None})
   if result is not None:
    layout=result;break
  if layout is not None:break
 if layout is None:
  report.update({'enabled':False,'autofit_failed':True,'autofit_attempts':attempts,'note':'侧壁无法容纳刻度，本任务已关闭海拔刻度'})
  for file in ('elevation_scale_vertices.bin','elevation_scale_faces.bin'):
   target=out/'web/layers'/file
   if target.exists():target.unlink()
  return None,report
 pieces,ticks,side,intervals=layout
 report.update({'side':side,'intervals':intervals,'ticks':ticks,'autofit_attempts':attempts})
 profile=profiles[side]-.6;length=float(size[0 if side in ('north','south') else 1]);u=np.linspace(0,length,len(profile))
 # A slab under the unchanged boundary profile clips all emboss to real side-wall area.
 poly=np.column_stack((np.r_[u,u[-1],u[0]],np.r_[profile,.8,.8]))
 slab=mf.CrossSection([poly[::-1]]).extrude(depth+embed)
 solid=mf.Manifold.batch_boolean(pieces,mf.OpType.Add)^slab
 assert solid.status()==mf.Error.NoError and solid.volume()>0
 solid=transform(solid)
 assert np.asarray(solid.to_mesh().vert_properties)[:,2].min()>0, 'Emboss must not alter flat bottom'
 mesh=solid.to_mesh()
 solid=mf.Manifold(mf.Mesh(np.array(mesh.vert_properties,dtype='f4',order='C'),np.array(mesh.tri_verts,dtype='u4',order='C'),face_id=np.full(len(mesh.tri_verts),8,dtype='u4')))
 mesh=solid.to_mesh();np.asarray(mesh.vert_properties,dtype='<f4')[:,:3].tofile(out/'web/layers/elevation_scale_vertices.bin');np.asarray(mesh.tri_verts,dtype='<u4').tofile(out/'web/layers/elevation_scale_faces.bin')
 report.update({'depth_mm':depth,'embed_mm':embed,'text_height_mm':h,'stroke_mm':t,'line_width_mm':tick,'vertices':len(mesh.vert_properties),'faces':len(mesh.tri_verts),'note':('Some ticks relocated and marked *; consult nominal_z_mm.' if any(t['relocated'] for t in report['ticks']) else 'All ticks at true altitude Z. S=start, E=end; recorded route altitude, not DEM sampled route altitude.')})
 return solid,report
