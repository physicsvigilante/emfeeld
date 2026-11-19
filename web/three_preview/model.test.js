import test from 'node:test';import assert from 'node:assert/strict';
import {displayTransform,toDisplay,savedFrame,potentialTriangles,validateSnapshot,replayIndex,browserNotes} from './model.js';
const fixture=()=>({visualization_version:1,title:'test',moving_slice:true,has_uniform_source:false,bounds_m:[10,14,20,24,30,34],
 units:{position:'m',time:'s',field:'N/C',potential:'V'},
 animation:{duration_s:2,samples:3,time_unit:'s',role:'saved_trajectory_sample_display_only'},geometry:[],annotations:[],missing_geometry:[],
 trajectories:[{id:'particle_0',marker_role:'schematic_particle_marker_not_physical_size_or_charge_sign',positions_m:[[10,20,30],[12,22,32],[14,24,34]],marker_radius_m:.1,
 role:'calculated_test_particle_trajectory_not_field_line'}],
 field:{positions_m:[[10,20,30]],vectors_SI:[[1,0,0]],unit:'N/C',role:'schematic_field_direction_glyphs_not_field_lines',schematic_arrows:{origins_m:[[10,20,30]],unit_directions:[[1,0,0]],display_length_m:.1,not_calibrated_field_lines:true}},
 potential:{role:'physical_potential_samples_on_display_slice',unit:'V',sample_order:'x_fastest_fortran',points_m:[[[10,20,32],[10,24,32]],[[14,20,32],[14,24,32]]],values:[10,11,20,21]}});
test('transform is display-only; physical data unchanged',()=>{const d=fixture(),before=JSON.stringify(d),t=displayTransform(d);assert.deepEqual(toDisplay([12,22,32],t),[0,0,0]);assert.deepEqual(toDisplay([14,24,34],t),[.5,.5,.5]);assert.equal(JSON.stringify(d),before);});
test('saved frame copies positions; no interpolation',()=>{const d=fixture(),f=savedFrame(d,1);assert.equal(f.time_s,1);f.positions_m[0][0]=-999;assert.equal(d.trajectories[0].positions_m[1][0],12);for(const bad of [-1,3,.5,NaN])assert.throws(()=>savedFrame(d,bad));});
test('potential corner values follow x-fastest order',()=>{const {triangles,omitted_cells}=potentialTriangles(fixture());assert.deepEqual(triangles.map(t=>t.map(p=>p.value)),[[10,11,21],[10,21,20]]);assert.equal(omitted_cells,0);});
test('null potential creates a hole, not a zero',()=>{const d=fixture();d.potential.values[1]=null;assert.deepEqual(potentialTriangles(d),{triangles:[],omitted_cells:1});assert.equal(d.potential.values[1],null);});
test('valid electric and gravity units admitted',()=>{const d=fixture();assert.equal(validateSnapshot(d),d);d.units.field=d.field.unit='m/s²';d.units.potential=d.potential.unit='J/kg';assert.equal(validateSnapshot(d),d);});
test('malformed versions/units/roles/timeline refused',()=>{for(const alter of [d=>d.visualization_version=2,d=>d.units.position='cm',d=>d.trajectories[0].role='field_line',d=>d.animation.samples=9,d=>d.field.schematic_arrows.unit_directions[0]=[0,0,0],d=>d.potential.sample_order='row_major',d=>d.potential.values[0]=Infinity]){const d=fixture();alter(d);assert.throws(()=>validateSnapshot(d));}});
test('display clock never selects a negative or out-of-range sample',()=>{assert.equal(replayIndex(0,-1,401),0);assert.equal(replayIndex(0,0,401),0);assert.equal(replayIndex(0,6000,401),200);assert.equal(replayIndex(20,-2,401),20);assert.equal(replayIndex(20,20000,401),400);assert.throws(()=>replayIndex(0,NaN,401));});

const source=(shape='point')=>({id:'source_0',shape,role:({point:'schematic_marker',sphere:'physical_extent',shell:'physical_extent',line:'truncated_infinite_source',plane:'truncated_infinite_source',none:'uniform_field_has_no_source_shape'})[shape],center_m:[12,22,32],radius_m:.1,direction:[0,0,1],display_span_m:4});
const rejects=(change,pattern)=>{const d=fixture();change(d);assert.throws(()=>validateSnapshot(d),pattern);};
test('all V1 source roles admitted without mutation',()=>{for(const shape of ['point','sphere','shell','line','plane','none']){const d=fixture();d.geometry=[source(shape)];d.has_uniform_source=shape==='none';const before=JSON.stringify(d);assert.equal(validateSnapshot(d),d);assert.equal(JSON.stringify(d),before);}});
test('contradictory and absent potential roles refused',()=>{for(const role of ['physical_material_surface',undefined])rejects(d=>d.potential.role=role,/potential/);});
test('contradictory and absent source roles refused',()=>{for(const role of ['physical_impenetrable_wall',undefined])rejects(d=>{d.geometry=[source()];d.geometry[0].role=role;},/source geometry role/);});
test('contradictory and absent marker roles refused',()=>{for(const role of ['actual_radius_and_charge_sign',undefined])rejects(d=>d.trajectories[0].marker_role=role,/trajectory/);});
test('annotation meaning and ids are required',()=>{for(const role of ['unknown',undefined])rejects(d=>d.annotations=[{id:'note',text:'note',role}],/annotations/);rejects(d=>d.annotations=[{text:'note',role:'display_annotation'}],/annotation id/);});
test('timeline time units required even when top-level units are SI',()=>{for(const value of ['years',undefined])rejects(d=>d.animation.time_unit=value,/timeline/);});
test('boolean display flags required, no truthy coercion',()=>{for(const key of ['moving_slice','has_uniform_source'])for(const value of [undefined,0,1,'false',null])rejects(d=>d[key]=value,/display flags/);rejects(d=>d.has_uniform_source=true,/uniform-source/);});
test('source and trajectory identities cannot be missing, empty or duplicated',()=>{for(const key of ['geometry','trajectories']){for(const id of [undefined,'',3])rejects(d=>{if(key==='geometry')d.geometry=[source()];d[key][0].id=id;},/id/);rejects(d=>{if(key==='geometry')d.geometry=[source()];d[key].push(structuredClone(d[key][0]));},/duplicate/);}});
test('infinite-source directions must already be normalized',()=>{for(const shape of ['line','plane'])for(const direction of [[0,0,0],[0,0,2],[1e-300,0,0],null])rejects(d=>{d.geometry=[source(shape)];d.geometry[0].direction=direction;},/infinite-source/);});
test('physical sample arrays have matching structure',()=>{rejects(d=>delete d.field.positions_m,/physical field/);rejects(d=>d.field.vectors_SI=[],/physical field/);rejects(d=>d.field.vectors_SI[0][0]=Infinity,/physical field/);const d=fixture();d.field.vectors_SI[0]=[null,null,null];validateSnapshot(d);});
test('same-sign huge finite bounds have a finite safe midpoint',()=>{const t=displayTransform({bounds_m:[1e308-3e306,1e308+3e306,-1,1,-1,1]});assert.ok(Number.isFinite(t.origin_m[0]));assert.equal(toDisplay([1e308,0,0],t)[0],0);});
test('unrepresentable span is refused, not made infinite',()=>{rejects(d=>d.bounds_m[0]=-Number.MAX_VALUE,/Unrenderable/);assert.throws(()=>displayTransform({bounds_m:[-1e308,1e308,-1,1,-1,1]}),/bounds span/);});
test('subnormal and unbounded rendered lengths refused in every actor family',()=>{for(const x of [Number.MIN_VALUE,1e100]){rejects(d=>d.field.schematic_arrows.display_length_m=x,/arrow length/);rejects(d=>d.trajectories[0].marker_radius_m=x,/marker length/);for(const shape of ['sphere','shell','line','plane'])rejects(d=>{d.geometry=[source(shape)];d.geometry[0][['sphere','shell'].includes(shape)?'radius_m':'display_span_m']=x;},/source (radius|span) length/);}});
test('all rendered coordinate families are checked before construction',()=>{for(const x of [1e308,1e8]){rejects(d=>{d.geometry=[source()];d.geometry[0].center_m[0]=x;},/source position/);rejects(d=>d.trajectories[0].positions_m[1][0]=x,/trajectory position/);rejects(d=>d.potential.points_m[0][0][0]=x,/potential position/);rejects(d=>d.field.schematic_arrows.origins_m[0][0]=x,/arrow position/);}});
test('binary32 coordinate underflow and tiny bounds aspect ratio refused',()=>{rejects(d=>{d.bounds_m=[-2,2,-2,2,-2,2];d.field.schematic_arrows.origins_m[0]=[Number.MIN_VALUE,0,0];},/arrow position/);rejects(d=>d.bounds_m=[-1,1,-Number.MIN_VALUE,Number.MIN_VALUE,-1,1],/bounds span/);});
test('browser notes replace only PyVista playback help without editing payload',()=>{const d=fixture();d.annotations=[{id:'playback_help',role:'display_annotation',text:'Space: play / pause; Home: restart; Left / Right'}, {id:'other',role:'display_annotation',text:'physical statement'}];const before=JSON.stringify(d),text=browserNotes(d);assert.match(text,/Play\/Pause button/);assert.ok(!/Space:|Home:|Left \/ Right/.test(text));assert.match(text,/physical statement/);assert.equal(JSON.stringify(d),before);});
function scaledFixture(scale,offset=0) {
  const d=fixture(),point=p=>p.map((x,i)=>x*scale+(i===0?offset:0));
  d.bounds_m=d.bounds_m.map((x,i)=>x*scale+(i<2?offset:0));
  d.trajectories.forEach(t=>{t.positions_m=t.positions_m.map(point);t.marker_radius_m*=scale;});
  d.field.positions_m=d.field.positions_m.map(point);
  d.field.schematic_arrows.origins_m=d.field.schematic_arrows.origins_m.map(point);
  d.field.schematic_arrows.display_length_m*=scale;
  d.potential.points_m=d.potential.points_m.map(row=>row.map(point));
  return d;
}
test('astronomical coordinates keep exact stored positions and saved time',()=>{const d=scaledFixture(1e11),before=JSON.stringify(d);validateSnapshot(d);assert.deepEqual(toDisplay(d.trajectories[0].positions_m[1],displayTransform(d)),[0,0,0]);assert.equal(savedFrame(d,1).time_s,1);assert.equal(JSON.stringify(d),before);});
test('coherently huge translated scene remains drawable without midpoint overflow',()=>{const d=scaledFixture(1e306,1e308),before=JSON.stringify(d);validateSnapshot(d);const t=displayTransform(d);assert.ok(t.origin_m.every(Number.isFinite));assert.ok(toDisplay(d.trajectories[0].positions_m[1],t).every(Number.isFinite));assert.equal(JSON.stringify(d),before);});
