"""Feature configuration and heightfield composition shared by build and combination tests."""
import copy,json,re
from pathlib import Path
import numpy as np
KEYS=('rivers','forest','grass','snow','houses','photos','elevation_scale')
def load_config(path,disable='',enable=''):
 cfg=json.loads(Path(path).read_text())
 for key in KEYS:
  if key not in cfg or type(cfg[key].get('enabled')) is not bool:raise ValueError(f'{key}.enabled must be boolean')
 for names,value in [(disable,False),(enable,True)]:
  for key in filter(None,(s.strip() for s in names.split(','))):
   if key not in KEYS:raise ValueError(f'Unknown feature: {key}')
   cfg[key]['enabled']=value
 def number(key,param,low,high):
  v=cfg[key][param]
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or not low<=v<=high:raise ValueError(f'{key}.{param} must be between {low} and {high}')
 number('rivers','depth_mm',.3,.6);number('rivers','river_width_mm',.7,6);number('rivers','stream_width_mm',.7,6)
 number('forest','raise_mm',.21,.5);number('forest','texture_mm',0,.29)
 if cfg['forest']['raise_mm']+cfg['forest']['texture_mm']>.5:raise ValueError('Forest maximum relief must be <= 0.5 mm')
 cfg['houses'].setdefault('route_gap_mm',4.0)
 number('houses','route_gap_mm',0,20)
 number('houses','sink_mm',.1,2);number('houses','scale',.2,3)
 cfg['houses'].setdefault('pin_color','#F4A7B9')
 if not re.fullmatch(r'#[0-9a-fA-F]{6}',cfg['houses']['pin_color']):raise ValueError('houses.pin_color must be #RRGGBB')
 cfg['houses'].setdefault('preview_color','#FFAE58')
 if not re.fullmatch(r'#[0-9a-fA-F]{6}',cfg['houses']['preview_color']):raise ValueError('houses.preview_color must be #RRGGBB')
 number('houses','min_route_clearance_mm',0,10)
 # Actual triangle-level clearance is checked during build; grid padding adds margin.
 if cfg['houses']['route_gap_mm']<1.7*cfg['houses']['scale']+1.5:raise ValueError('route_gap_mm must exceed scaled house half width + 1.5 mm')
 if type(cfg['houses']['include_uncertain']) is not bool:raise ValueError('houses.include_uncertain must be boolean')
 cfg['elevation_scale'].setdefault('source','route_start_end')
 if cfg['elevation_scale']['source'] not in ('route_start_end','terrain_min_max'):raise ValueError('Invalid elevation_scale.source')
 number('elevation_scale','intervals',1,10)
 if type(cfg['elevation_scale']['intervals']) is not int:raise ValueError('elevation_scale.intervals must be integer')
 if cfg['elevation_scale']['side'] not in ('south','north','east','west'):raise ValueError('Invalid elevation_scale.side')
 for key,low,high in [('depth_mm',.3,.6),('line_width_mm',.5,2),('tick_length_mm',3,20),('text_height_mm',4,10),('stroke_mm',.5,1.2)]:number('elevation_scale',key,low,high)
 if not re.fullmatch(r'#[0-9a-fA-F]{6}',cfg['elevation_scale']['color']):raise ValueError('Invalid elevation scale color')
 return cfg

def compose(base,classes,forest_delta,water_delta,house_top,dist,state,route_gap=None):
 """Only vertical vertex positions change, preserving the closed grid topology."""
 surface=base.copy();category=np.zeros(base.shape,dtype=np.uint8)
 if state['forest']:
  surface+=forest_delta;category[classes==2]=2
 if state['rivers']:
  water=classes==1;surface[water]=base[water]+water_delta[water];category[water]=1
 if state['grass']:category[classes==5]=5
 if state['snow']:category[classes==3]=3
 if state['houses']:
  house=house_top>0;surface[house]=np.maximum(surface[house],house_top[house]);category[house]=6
 floor=np.maximum(base,surface)
 gap=np.zeros(base.shape,dtype=bool) if route_gap is None or not state['houses'] else np.asarray(route_gap,dtype=bool)
 weight=np.where(gap,0,np.clip((.85-dist)/.13,0,1))
 z=surface+weight*(floor-surface+.8)
 active_route=(dist<.72)&~gap
 category[active_route]=4
 assert np.all(np.isfinite(z)) and np.min(z)>.8
 assert not np.any(active_route) or np.min((z-floor)[active_route])>=.79999
 assert np.allclose(z[gap],surface[gap]) and not np.any(category[gap]==4)
 return z,category,surface


def route_circle_length(route,center,radius):
 """Ordered polyline centerline length inside a circle, in model millimeters.
 Repeated traversal counts repeatedly; this is horizontal distance, not 3D hiking distance.
 """
 route=np.asarray(route,dtype=float);center=np.asarray(center,dtype=float)
 a=route[:-1]-center;d=np.diff(route,axis=0);aa=np.sum(d*d,axis=1)
 bb=2*np.sum(a*d,axis=1);cc=np.sum(a*a,axis=1)-radius*radius
 disc=bb*bb-4*aa*cc;valid=(aa>0)&(disc>=0)
 t0=np.zeros(len(aa));t1=np.zeros(len(aa))
 root=np.sqrt(np.maximum(disc[valid],0));t0[valid]=(-bb[valid]-root)/(2*aa[valid]);t1[valid]=(-bb[valid]+root)/(2*aa[valid])
 return float(np.sum(np.sqrt(aa[valid])*np.maximum(0,np.minimum(1,t1[valid])-np.maximum(0,t0[valid]))))
