import test from 'node:test';import assert from 'node:assert/strict';
import {displayTransform,toDisplay,savedFrame,potentialTriangles,validateSnapshot} from './model.js';
const fixture=()=>({visualization_version:1,title:'test',bounds_m:[10,14,20,24,30,34],
 units:{position:'m',time:'s',field:'N/C',potential:'V'},
 animation:{duration_s:2,samples:3,role:'saved_trajectory_sample_display_only'},geometry:[],annotations:[],missing_geometry:[],
 trajectories:[{positions_m:[[10,20,30],[12,22,32],[14,24,34]],marker_radius_m:.1,
 role:'calculated_test_particle_trajectory_not_field_line'}],
 field:{unit:'N/C',role:'schematic_field_direction_glyphs_not_field_lines',schematic_arrows:{origins_m:[[10,20,30]],unit_directions:[[1,0,0]],display_length_m:.1,not_calibrated_field_lines:true}},
 potential:{unit:'V',sample_order:'x_fastest_fortran',points_m:[[[10,20,32],[10,24,32]],[[14,20,32],[14,24,32]]],values:[10,11,20,21]}});
test('transform is display-only; physical data unchanged',()=>{const d=fixture(),before=JSON.stringify(d),t=displayTransform(d);assert.deepEqual(toDisplay([12,22,32],t),[0,0,0]);assert.deepEqual(toDisplay([14,24,34],t),[.5,.5,.5]);assert.equal(JSON.stringify(d),before);});
test('saved frame copies positions; no interpolation',()=>{const d=fixture(),f=savedFrame(d,1);assert.equal(f.time_s,1);f.positions_m[0][0]=-999;assert.equal(d.trajectories[0].positions_m[1][0],12);for(const bad of [-1,3,.5,NaN])assert.throws(()=>savedFrame(d,bad));});
test('potential corner values follow x-fastest order',()=>{const {triangles,omitted_cells}=potentialTriangles(fixture());assert.deepEqual(triangles.map(t=>t.map(p=>p.value)),[[10,11,21],[10,21,20]]);assert.equal(omitted_cells,0);});
test('null potential creates a hole, not a zero',()=>{const d=fixture();d.potential.values[1]=null;assert.deepEqual(potentialTriangles(d),{triangles:[],omitted_cells:1});assert.equal(d.potential.values[1],null);});
test('valid electric and gravity units admitted',()=>{const d=fixture();assert.equal(validateSnapshot(d),d);d.units.field=d.field.unit='m/s²';d.units.potential=d.potential.unit='J/kg';assert.equal(validateSnapshot(d),d);});
test('malformed versions/units/roles/timeline refused',()=>{for(const alter of [d=>d.visualization_version=2,d=>d.units.position='cm',d=>d.trajectories[0].role='field_line',d=>d.animation.samples=9,d=>d.field.schematic_arrows.unit_directions[0]=[0,0,0],d=>d.potential.sample_order='row_major',d=>d.potential.values[0]=Infinity]){const d=fixture();alter(d);assert.throws(()=>validateSnapshot(d));}});
