import json, numpy as np, trimesh
import manifold3d as mf
M = mf.Manifold
E = 0.01  # overlap to guarantee fused unions

def box(x0,y0,z0,x1,y1,z1):
    return M.cube([x1-x0,y1-y0,z1-z0]).translate([x0,y0,z0])
def hull(pts):
    return M.hull_points(np.asarray(pts, dtype=np.float64))
def gable(x0,x1,y0,y1,z0,z1):
    """gable roof prism, ridge along x"""
    yc=(y0+y1)/2
    return hull([[x0,y0,z0],[x1,y0,z0],[x0,y1,z0],[x1,y1,z0],[x0,yc,z1],[x1,yc,z1]])
def frustum_box(bx,by,tx,ty,z0,z1):
    return hull([[sx*bx/2,sy*by/2,z0] for sx in(-1,1) for sy in(-1,1)]+[[sx*tx/2,sy*ty/2,z1] for sx in(-1,1) for sy in(-1,1)])
def cyl(h,r0,r1,z0,seg=16,x=0,y=0):
    return M.cylinder(h,r0,r1,seg).translate([x,y,z0])

DESIGNS = {}
def design(key,name,desc,colors):
    def deco(f):
        DESIGNS[key]=dict(name=name,desc=desc,colors=colors,fn=f); return f
    return deco

# ---------- 1 classic monopoly house ----------
@design('1_monopoly_house','经典大富翁','大富翁绿房子：方盒子+人字顶+烟囱，白色门窗',
        {'body':'#2e9e4f','accent':'#f7f7f2'})
def d1():
    P=[]
    W,D=3.4,2.8; H=2.0; R=3.5
    P+= [('body',box(-W/2,-D/2,0,W/2,D/2,H+E))]
    P+= [('body',gable(-W/2,W/2,-D/2,D/2,H,R))]
    P+= [('body',box(0.55,-0.1,2.3,1.15,0.5,3.95))]          # chimney 0.6x0.6
    t=0.15
    P+= [('accent',box(-0.4,-D/2-t,0,0.4,-D/2+E,1.15))]         # door
    P+= [('accent',box(0.75,-D/2-t,0.7,1.3,-D/2+E,1.25))]       # front window
    P+= [('accent',box(-1.3,-D/2-t,0.7,-0.75,-D/2+E,1.25))]
    for s in(-1,1):                                             # gable windows
        x=s*W/2; P+= [('accent',box(min(x,x+s*t)-(E if s>0 else 0),-0.3,1.4,max(x,x+s*t)+(E if s<0 else 0),0.3,2.0))]
    return P

# ---------- 2 monopoly hotel ----------
@design('2_monopoly_hotel','红色酒店','大富翁红酒店：长条楼身+人字顶，两排白窗',
        {'body':'#d6332b','accent':'#f7f7f2'})
def d2():
    P=[]; W,D,H,R=4.0,2.4,2.4,3.4
    P+= [('body',box(-W/2,-D/2,0,W/2,D/2,H+E)),('body',gable(-W/2,W/2,-D/2,D/2,H,R))]
    t=0.15; y0=-D/2-t; y1=-D/2+E
    for x in(-1.3,0,1.3): P+= [('accent',box(x-0.27,y0,1.5,x+0.27,y1,2.05))]
    for x in(-1.3,1.3): P+= [('accent',box(x-0.27,y0,0.55,x+0.27,y1,1.1))]
    P+= [('accent',box(-0.35,y0,0,0.35,y1,1.15))]
    return P

# ---------- 3 mushroom cottage ----------
@design('3_mushroom_cottage','蘑菇小屋','圆筒小屋配超大红色尖顶，童话感最强',
        {'body':'#f2e2bf','accent':'#e2463b'})
def d3():
    P=[]
    P+= [('body',cyl(1.65,1.3,1.3,0,16))]
    P+= [('accent',cyl(0.45+E,1.3,1.85,1.25,16))]          # 45deg-ish flare, no flat overhang
    P+= [('accent',cyl(2.3,1.85,0.22,1.7,16))]             # big cone roof
    P+= [('accent',box(-0.38,-1.45,0,0.38,-1.1,1.05))]     # door
    P+= [('accent',box(0.95,-0.95,0.55,1.5,-0.4,1.05).rotate([0,0,0]))] if False else []
    return P

# ---------- 4 tibetan house ----------
@design('4_tibetan_house','藏式民居','收分白墙+红色边玛檐口与梯形窗，屋顶一座小白塔',
        {'body':'#f5f2ea','accent':'#8a2a22'})
def d4():
    P=[]
    P+= [('body',frustum_box(3.4,3.0,3.06,2.66,0,2.2+E))]
    P+= [('accent',frustum_box(3.06,2.66,3.0,2.6,2.2,2.6))]           # bianma band
    for sx in(-1,1):
        for sy in(-1,1):                                               # corner merlons
            P+= [('accent',box(sx*1.5-0.25-E*sx,sy*1.3-0.25,2.6-E,sx*1.5+0.25,sy*1.3+0.25,3.0))] if True else []
    # trapezoid windows / door on the front (y-) face, slab straddles the battered wall
    def win(xc,z0,z1,wb,wt):
        return ('accent',hull([[xc-wb/2,-1.62,z0],[xc+wb/2,-1.62,z0],[xc-wt/2,-1.62,z1],[xc+wt/2,-1.62,z1],
                               [xc-wb/2,-1.1,z0],[xc+wb/2,-1.1,z0],[xc-wt/2,-1.1,z1],[xc+wt/2,-1.1,z1]]))
    P+= [win(-0.95,1.1,1.75,0.7,0.5), win(0.95,1.1,1.75,0.7,0.5), win(0,0,1.0,0.8,0.65)]
    # little white stupa on the roof
    P+= [('body',box(-0.55,-0.55,2.6-E,0.55,0.55,3.0))]
    P+= [('body',cyl(0.5,0.48,0.42,3.0-E,12))]
    P+= [('body',M.sphere(0.45,12).scale([1,1,0.9]).translate([0,0,3.55]))]
    P+= [('accent',cyl(0.6,0.24,0.2,3.85,10))]                 # spire (>=0.4 dia)
    return P

# ---------- 5 map pin house ----------
@design('5_pin_house','地图图钉屋','红色地图图钉托着一栋白墙红顶小房子，最像“标注点”',
        {'body':'#f7f7f2','accent':'#e2463b'})
def d5():
    P=[]
    P+= [('accent',cyl(1.6+E,0.55,1.7,0,20))]               # pin cone (37deg from vertical)
    P+= [('accent',cyl(0.3,1.7,1.7,1.6,20))]                # pin disc
    P+= [('body',box(-1.0,-0.8,1.9-E,1.0,0.8,2.95+E))]       # walls
    P+= [('accent',gable(-1.15,1.15,-0.95,0.95,2.95,3.95))] # roof (0.15 eave, chamfer-free but tiny)
    P+= [('accent',box(-0.3,-0.95,1.9,0.3,-0.8+E,2.65))]    # door
    return P

def build(key,spec):
    parts=spec['fn']()
    ids={}; ms=[]
    for role,m in parts:
        m=m.as_original(); ids[m.original_id()]=role; ms.append(m)
    u=M.batch_boolean(ms, mf.OpType.Add)
    mesh=u.to_mesh()
    v=np.asarray(mesh.vert_properties)[:,:3]; f=np.asarray(mesh.tri_verts)
    ri=np.asarray(mesh.run_index)//3; ro=np.asarray(mesh.run_original_id)
    roles=np.empty(len(f),dtype=object)
    for i,oid in enumerate(ro): roles[ri[i]:ri[i+1]]=ids.get(int(oid),'body')
    tm=trimesh.Trimesh(v,f,process=True)
    return tm, roles, u

def hex2rgba(h): return [int(h[i:i+2],16) for i in (1,3,5)]+[255]

report=[]
for key,spec in DESIGNS.items():
    tm,roles,u=build(key,spec)
    tm.export(f'{key}.stl')
    # colored GLB: one node per color, flat-shaded (unmerged)
    sc=trimesh.Scene()
    for role,hexc in spec['colors'].items():
        sel=np.where(roles==role)[0]
        if len(sel)==0: continue
        sub=tm.submesh([sel],append=True); sub.unmerge_vertices()
        mat=trimesh.visual.material.PBRMaterial(name=role,baseColorFactor=hex2rgba(hexc),metallicFactor=0.0,roughnessFactor=0.75)
        sub.visual=trimesh.visual.TextureVisuals(material=mat)
        sc.add_geometry(sub,node_name=role,geom_name=f'{key}_{role}')
    sc.export(f'{key}.glb')
    b=tm.bounds; ext=b[1]-b[0]
    r=dict(key=key,name=spec['name'],desc=spec['desc'],colors=spec['colors'],
           size_mm=[round(float(x),2) for x in ext],zmin=round(float(b[0][2]),4),
           triangles=int(len(tm.faces)),watertight=bool(tm.is_watertight),
           winding_consistent=bool(tm.is_winding_consistent),bodies=len(tm.split(only_watertight=False)),
           manifold_genus=u.genus(),volume_mm3=round(float(tm.volume),2),
           faces_by_color={k:int((roles==k).sum()) for k in spec['colors']})
    report.append(r); print(r)
json.dump(report,open('designs.json','w'),ensure_ascii=False,indent=1)
