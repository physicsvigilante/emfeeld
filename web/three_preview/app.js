import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { validateSnapshot, displayTransform, toDisplay, savedFrame, potentialTriangles } from './model.js';

const $=id=>document.getElementById(id), host=$('canvas');
let data, transform, sourceRecord, group, markers=[], arrows=[], potentialMesh, lastIndex=0;
let playing=false, startMs=0, startIndex=0, omitted=0, manifest;
let renderer, camera, controls, world;
const vec=a=>new THREE.Vector3(...a);
const display=v=>vec(toDisplay(v,transform));
const bytesHash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)))
  .map(x=>x.toString(16).padStart(2,'0')).join('');
function fail(error){
  playing=false; $('play').textContent='Play'; $('play').disabled=true; $('frame').disabled=true;
  $('error').hidden=false; $('error').textContent='Preview unavailable: '+error.message;
  if(group) {clearGroup(); renderer.render(world,camera);}
  window.emfeeldPreviewError=error.message;
}
function clearGroup(){
  if(!group)return;
  world.remove(group);
  group.traverse(o=>{o.geometry?.dispose();
    if(o.material){const materials=Array.isArray(o.material)?o.material:[o.material];
      for(const m of materials){m.map?.dispose();m.dispose();}}});
  group=null;markers=[];arrows=[];potentialMesh=null;
}
function line(points,color,width=1){
  const mesh=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({color,linewidth:width}));group.add(mesh);return mesh;
}
function sphere(position,radius,color,opacity=1,wireframe=false){
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(radius,20,16),new THREE.MeshBasicMaterial({
    color,transparent:opacity<1,opacity,wireframe,depthWrite:opacity===1}));
  mesh.position.copy(position);group.add(mesh);return mesh;
}
function label(text,position){
  const c=document.createElement('canvas');c.width=96;c.height=48;
  const context=c.getContext('2d');context.fillStyle='#17364b';context.font='28px sans-serif';
  context.fillText(text,10,34);
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:false}));
  s.position.copy(position);s.scale.set(.1,.05,1);group.add(s);
}
function construct(){
  clearGroup();group=new THREE.Group();world.add(group);transform=displayTransform(data);
  for(const g of data.geometry){
    const c=display(g.center_m);
    if(g.shape==='point')sphere(c,.012,0x526572);
    if(g.shape==='sphere'||g.shape==='shell')sphere(c,g.radius_m/transform.scale_m,0xa6b6c1,.18,g.shape==='shell');
    if(g.shape==='line'){
      const a=vec(g.direction).multiplyScalar(g.display_span_m/transform.scale_m);
      line([c.clone().sub(a),c.clone().add(a)],0x526572);
    }
    if(g.shape==='plane'){
      const side=g.display_span_m/transform.scale_m;
      const mesh=new THREE.Mesh(new THREE.PlaneGeometry(side,side),new THREE.MeshBasicMaterial({
        color:0x9cabb5,transparent:true,opacity:.12,side:THREE.DoubleSide,depthWrite:false}));
      mesh.position.copy(c);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),vec(g.direction));group.add(mesh);
    }
    // Uniform fields intentionally have no material source mesh.
  }
  const sampled=data.field.schematic_arrows;
  sampled.origins_m.forEach((p,i)=>{
    const length=sampled.display_length_m/transform.scale_m;
    const a=new THREE.ArrowHelper(vec(sampled.unit_directions[i]),display(p),length,0x647380,length*.3,length*.15);
    group.add(a);arrows.push(a);
  });
  for(const t of data.trajectories){
    line(t.positions_m.map(display),0x202a30);
    markers.push(sphere(display(t.positions_m[0]),t.marker_radius_m/transform.scale_m,0xc323a7));
  }
  const surface=potentialTriangles(data);omitted=surface.omitted_cells;
  const finite=data.potential.values.filter(v=>v!==null);
  if(finite.length){
    const lo=Math.min(...finite),hi=Math.max(...finite),positions=[],colors=[];
    for(const triangle of surface.triangles)for(const v of triangle){
      positions.push(...display(v.position_m).toArray());
      // Color interpolation only, not a new field estimate or physics value.
      const fraction=hi===lo ? .5 :(v.value-lo)/(hi-lo);
      const color=new THREE.Color().setHSL((1-fraction)*.66,.7,.54);colors.push(color.r,color.g,color.b);
    }
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
    potentialMesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({vertexColors:true,
      transparent:true,opacity:data.moving_slice ? .35 : .7,side:THREE.DoubleSide,depthWrite:false}));
    potentialMesh.visible=$('potential').checked;group.add(potentialMesh);
    $('range').textContent=`Potential [${data.units.potential}]: blue ${lo.toPrecision(5)} → red ${hi.toPrecision(5)}. ${omitted} undefined cells omitted.`;
  }else $('range').textContent='Potential unavailable on this slice; no scalar surface drawn.';
  const axesOrigin=new THREE.Vector3(-.5,-.5,-.5);
  [[1,0,0],[0,1,0],[0,0,1]].forEach((a,i)=>{
    group.add(new THREE.ArrowHelper(vec(a),axesOrigin,.2,[0xad5252,0x308c68,0x3b73a3][i],.025,.012));
    label(['x','y','z'][i],axesOrigin.clone().addScaledVector(vec(a),.24));
  });
  $('title').textContent=data.title;
  $('notes').textContent=data.annotations.map(a=>a.text).join('\n\n')+
      (data.missing_geometry.length?'\nUndrawn sources: '+data.missing_geometry.join(', '):'');
  $('provenance').textContent=`Snapshot SHA-256: ${sourceRecord.sha256}\nSchema: VisualizationData V1\n`
    +`Source example: ${sourceRecord.input}\nField: ${data.units.field}; position: m\n`
    +`Display transform: (world-origin)/scale\nOrigin [m]: ${transform.origin_m}\nScale [m]: ${transform.scale_m}\n`
    +'No browser-side field law or integrator.';
  $('frame').max=data.animation.samples-1;setFrame(0);
  $('frame').disabled=$('play').disabled=!markers.length;$('reset').disabled=false;
  resetCamera();
}
function setFrame(index){
  const frame=savedFrame(data,index);lastIndex=index;$('frame').value=index;
  markers.forEach((m,i)=>m.position.copy(display(frame.positions_m[i])));
  $('time').textContent=`Sample ${index} / ${data.animation.samples-1} · physical time ${frame.time_s.toPrecision(7)} s`;
  $('positions').textContent=frame.positions_m.map((p,i)=>`Particle ${i+1} [m]\n(${p.map(v=>v.toPrecision(7)).join(', ')})`).join('\n');
}
function resetCamera(){camera.position.set(1.45,-1.8,1.3);camera.up.set(0,0,1);controls.target.set(0,0,0);controls.update();}
function resize(){const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}
async function loadScene(index){
  playing=false;$('play').textContent='Play';$('scene').disabled=true;$('error').hidden=true;
  try{
    sourceRecord=manifest.scenes[index];const response=await fetch(sourceRecord.file);
    if(!response.ok)throw Error('Snapshot request failed');const bytes=await response.arrayBuffer();
    if(await bytesHash(bytes)!==sourceRecord.sha256)throw Error('Snapshot checksum mismatch');
    data=validateSnapshot(JSON.parse(new TextDecoder().decode(bytes)));construct();
  }finally{$('scene').disabled=false;}
}
try{
  world=new THREE.Scene();world.background=new THREE.Color(0xffffff);
  camera=new THREE.PerspectiveCamera(40,1,.001,100);camera.up.set(0,0,1);
  renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.appendChild(renderer.domElement);
  controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
  new ResizeObserver(resize).observe(host);resize();
  const response=await fetch('manifest.json');if(!response.ok)throw Error('Export manifest unavailable');manifest=await response.json();
  manifest.scenes.forEach((s,i)=>{const option=document.createElement('option');option.value=i;option.textContent=s.title;$('scene').append(option);});
  $('scene').addEventListener('change',()=>loadScene(Number($('scene').value)).catch(fail));
  $('frame').addEventListener('input',()=>{playing=false;$('play').textContent='Play';setFrame(Number($('frame').value));});
  $('potential').addEventListener('change',()=>{if(potentialMesh)potentialMesh.visible=$('potential').checked;});
  $('reset').addEventListener('click',resetCamera);
  $('play').addEventListener('click',()=>{
    playing=!playing;if(playing){if(lastIndex===data.animation.samples-1)setFrame(0);startIndex=lastIndex;startMs=performance.now();}
    $('play').textContent=playing?'Pause':'Play';
  });
  await loadScene(0);
  // Inspection hook returns copies/current THREE actor transforms, not a physics API.
  window.emfeeldPreview={inspect:()=>({three_revision:THREE.REVISION,
    webgl_version:renderer.getContext().getParameter(renderer.getContext().VERSION),
    snapshot:structuredClone(data),frame:savedFrame(data,lastIndex),transform:structuredClone(transform),
    marker_display:markers.map(m=>m.position.toArray()),arrow_origins:arrows.map(a=>a.position.toArray()),
    omitted_cells:omitted,source:structuredClone(sourceRecord),camera:camera.position.toArray()}),
    setFrame};
  function tick(now){requestAnimationFrame(tick);
    if(playing){const next=Math.min(data.animation.samples-1,startIndex+Math.floor((now-startMs)/12000*(data.animation.samples-1)));
      if(next!==lastIndex)setFrame(next);if(next===data.animation.samples-1){playing=false;$('play').textContent='Play';}}
    controls.update();renderer.render(world,camera);
  }
  requestAnimationFrame(tick);
}catch(error){fail(error);}
