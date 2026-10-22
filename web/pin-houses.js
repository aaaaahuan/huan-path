// Small local GLB reader for the untextured, triangle-only house designs.
// Reject unsupported layouts rather than silently changing a replacement design.
export async function loadPinHouse(THREE,url){
 const response=await fetch(url);if(!response.ok)throw Error(`房屋模型加载失败 ${url}`);
 const buffer=await response.arrayBuffer(),view=new DataView(buffer);
 if(view.getUint32(0,true)!==0x46546c67||view.getUint32(4,true)!==2)throw Error('需要 GLB 2.0');
 let doc,bin;
 for(let offset=12;offset<buffer.byteLength;){const length=view.getUint32(offset,true),type=view.getUint32(offset+4,true);offset+=8;
  if(type===0x4e4f534a)doc=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,offset,length)));
  if(type===0x004e4942)bin=buffer.slice(offset,offset+length);offset+=length;
 }
 function accessor(index){const a=doc.accessors[index],b=doc.bufferViews[a.bufferView],types={5126:Float32Array,5125:Uint32Array,5123:Uint16Array,5121:Uint8Array},sizes={SCALAR:1,VEC3:3,VEC2:2,VEC4:4};
  if(a.sparse||b.byteStride||b.buffer!==0||!types[a.componentType]||!sizes[a.type])throw Error('房屋 GLB 使用不支持的 accessor 布局');
  return new types[a.componentType](bin,(b.byteOffset||0)+(a.byteOffset||0),a.count*sizes[a.type]).slice();
 }
 function node(index){const n=doc.nodes[index],group=new THREE.Group();
  if(n.matrix){group.matrix.fromArray(n.matrix);group.matrixAutoUpdate=false}else{if(n.translation)group.position.fromArray(n.translation);if(n.rotation)group.quaternion.fromArray(n.rotation);if(n.scale)group.scale.fromArray(n.scale)}
  if(n.mesh!==undefined)for(const p of doc.meshes[n.mesh].primitives){if((p.mode??4)!==4)throw Error('房屋 GLB 必须是三角面');
   const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(accessor(p.attributes.POSITION),3));if(p.indices!==undefined)geometry.setIndex(new THREE.BufferAttribute(accessor(p.indices),1));geometry.computeVertexNormals();
   const m=doc.materials[p.material]?.pbrMetallicRoughness||{},c=m.baseColorFactor||[1,1,1,1];
   const material=new THREE.MeshStandardMaterial({color:new THREE.Color().setRGB(c[0],c[1],c[2],THREE.SRGBColorSpace),roughness:m.roughnessFactor??.75,metalness:m.metallicFactor??0});
   material.name=doc.materials[p.material]?.name||'';
   const mesh=new THREE.Mesh(geometry,material);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);
  }for(const child of n.children||[])group.add(node(child));return group;
 }
 const result=new THREE.Group();for(const i of doc.scenes[doc.scene||0].nodes)result.add(node(i));return result;
}
