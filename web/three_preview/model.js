/** Rendering-only helpers. No field law, force law, integrator or interpolation. */
const finite = x => typeof x === 'number' && Number.isFinite(x);
const vec = v => Array.isArray(v) && v.length === 3 && v.every(finite);
const unit = v => vec(v) && Math.abs(Math.hypot(...v)-1) < 1e-12;
const sourceRoles = {
  point:'schematic_marker', sphere:'physical_extent', shell:'physical_extent',
  line:'truncated_infinite_source', plane:'truncated_infinite_source',
  none:'uniform_field_has_no_source_shape'
};
function identified(items, label) {
  if (!Array.isArray(items)) throw Error(`Invalid ${label} list`);
  const ids = new Set();
  for (const item of items) {
    if (!item || typeof item.id !== 'string' || !item.id.trim() || ids.has(item.id))
      throw Error(`Invalid or duplicate ${label} id`);
    ids.add(item.id);
  }
}
export function validateSnapshot(d) {
  if (d?.visualization_version !== 1 || typeof d.title !== 'string') throw Error('Unsupported visualization snapshot');
  const transform = displayTransform(d);
  if (d.units?.position !== 'm' || d.units?.time !== 's') throw Error('Only SI metre/second snapshots supported');
  if (!(d.units.field === 'N/C' && d.units.potential === 'V')
      && !(d.units.field === 'm/s²' && d.units.potential === 'J/kg')) throw Error('Unsupported physical units');
  if (typeof d.moving_slice !== 'boolean' || typeof d.has_uniform_source !== 'boolean')
    throw Error('Invalid display flags');
  if (!Number.isSafeInteger(d.animation?.samples) || d.animation.samples < 2
      || !finite(d.animation.duration_s) || d.animation.duration_s <= 0
      || d.animation.time_unit !== 's'
      || d.animation.role !== 'saved_trajectory_sample_display_only') throw Error('Invalid saved timeline');
  identified(d.geometry, 'source');
  for (const g of d.geometry) {
    if (!vec(g.center_m) || !Object.hasOwn(sourceRoles,g.shape)) throw Error('Unsupported source geometry');
    if (g.role !== sourceRoles[g.shape]) throw Error('Invalid source geometry role');
    if (['sphere','shell'].includes(g.shape) && (!finite(g.radius_m) || g.radius_m <= 0)) throw Error('Invalid radius');
    if (['line','plane'].includes(g.shape) && (!unit(g.direction)
        || !finite(g.display_span_m) || g.display_span_m <= 0)) throw Error('Invalid infinite-source patch');
  }
  if (d.has_uniform_source !== d.geometry.some(g=>g.shape==='none')) throw Error('Inconsistent uniform-source flag');
  identified(d.trajectories, 'trajectory');
  if (d.trajectories.some(t => t.role !== 'calculated_test_particle_trajectory_not_field_line'
      || t.marker_role !== 'schematic_particle_marker_not_physical_size_or_charge_sign'
      || !Array.isArray(t.positions_m) || t.positions_m.length !== d.animation.samples
      || !t.positions_m.every(vec) || !finite(t.marker_radius_m) || t.marker_radius_m <= 0)) throw Error('Invalid saved trajectory');
  const a = d.field?.schematic_arrows;
  if (d.field?.unit !== d.units.field || d.field.role !== 'schematic_field_direction_glyphs_not_field_lines'
      || !a || a.not_calibrated_field_lines !== true || !finite(a.display_length_m) || a.display_length_m <= 0
      || !Array.isArray(a.origins_m) || !Array.isArray(a.unit_directions)
      || a.origins_m.length !== a.unit_directions.length || !a.origins_m.every(vec)
      || !a.unit_directions.every(unit)) throw Error('Invalid schematic field arrows');
  if (!Array.isArray(d.field.positions_m) || !d.field.positions_m.every(vec)
      || !Array.isArray(d.field.vectors_SI) || d.field.vectors_SI.length !== d.field.positions_m.length
      || !d.field.vectors_SI.every(v=>Array.isArray(v) && v.length===3 && v.every(x=>x===null || finite(x))))
    throw Error('Invalid physical field samples');
  const p = d.potential, nx = p?.points_m?.length, ny = p?.points_m?.[0]?.length;
  if (p?.unit !== d.units.potential || p.role !== 'physical_potential_samples_on_display_slice'
      || p.sample_order !== 'x_fastest_fortran' || !Array.isArray(p.points_m) || nx < 2 || ny < 2
      || !p.points_m.every(row => Array.isArray(row) && row.length === ny && row.every(vec))
      || !Array.isArray(p.values) || p.values.length !== nx*ny
      || !p.values.every(v => v === null || finite(v))) throw Error('Invalid potential slice');
  identified(d.annotations, 'annotation');
  if (d.annotations.some(a => typeof a.text !== 'string' || a.role !== 'display_annotation')
      || !Array.isArray(d.missing_geometry) || d.missing_geometry.some(s => typeof s !== 'string')) throw Error('Invalid annotations');
  validateDisplay(d, transform);
  return d;
}

export function displayTransform(d) {
  const b=d?.bounds_m;
  if (!Array.isArray(b) || b.length!==6 || !b.every(finite)
      || [0,2,4].some(i=>b[i]>=b[i+1])) throw Error('Invalid bounds');
  const spans=[0,2,4].map(i=>b[i+1]-b[i]);
  if (!spans.every(x=>finite(x) && x>0)) throw Error('Unrenderable bounds span');
  // Unlike (lo+hi)/2, this cannot overflow for a representable ordered span.
  return {origin_m:[0,2,4].map((i,k)=>b[i]+spans[k]/2),scale_m:Math.max(...spans)};
}
export const toDisplay = (v,t) => v.map((x,i)=>(x-t.origin_m[i])/t.scale_m);
function validateDisplay(d,t) {
  // Explicit prototype domain, not a physical limit or a promise of pixel visibility.
  const coordinate = x => finite(x) && Math.abs(x)<=1e6
    && Number.isFinite(Math.fround(x)) && (x===0 || Math.fround(x)!==0);
  const point = (v,label) => {
    const result=toDisplay(v,t);
    if (!result.every(coordinate) || result.some((x,i)=>x===0 && v[i]!==t.origin_m[i]))
      throw Error(`Unrenderable ${label} position`);
    return result;
  };
  const length = (value,label,minimum=1e-6) => {
    const x=value/t.scale_m;
    if (!finite(x) || x<minimum || x>1e3) throw Error(`Unrenderable ${label} length`);
    return x;
  };
  for (let axis=0;axis<3;axis++) {
    const span=(d.bounds_m[2*axis+1]-d.bounds_m[2*axis])/t.scale_m;
    if (!coordinate(span) || span===0) throw Error('Unrenderable bounds span');
  }
  for (const g of d.geometry) {
    const center=point(g.center_m,'source');
    let extent=0;
    if (['sphere','shell'].includes(g.shape)) extent=length(g.radius_m,'source radius');
    if (['line','plane'].includes(g.shape)) extent=length(g.display_span_m,'source span');
    if (center.some(x=>!coordinate(x-extent) || !coordinate(x+extent))) throw Error('Unrenderable source extent');
  }
  for (const path of d.trajectories) {
    length(path.marker_radius_m,'marker');
    path.positions_m.forEach(p=>point(p,'trajectory'));
  }
  const a=d.field.schematic_arrows;
  // Three.js ArrowHelper floors its shaft at 0.0001; do not silently stretch tiny arrows.
  length(a.display_length_m,'arrow',1e-3);
  a.origins_m.forEach(p=>point(p,'arrow'));
  d.potential.points_m.forEach(row=>row.forEach(p=>point(p,'potential')));
}
export function browserNotes(d) {
  return d.annotations.map(a=>a.id==='playback_help'
    ? 'Use the Play/Pause button and saved-sample slider. Drag/touch to orbit.\nReplay is display time, not physical time.'
    : a.text).join('\n\n');
}
export function savedFrame(d,index) {
  if (!Number.isInteger(index) || index<0 || index>=d.animation.samples) throw Error('Invalid saved frame');
  return {index, time_s:d.animation.duration_s*(index/(d.animation.samples-1)),
          positions_m:d.trajectories.map(t=>t.positions_m[index].slice())};
}
export function potentialTriangles(d) {
  const p=d.potential, nx=p.points_m.length, ny=p.points_m[0].length;
  const triangles=[]; let omitted=0;
  for(let y=0;y<ny-1;y++) for(let x=0;x<nx-1;x++) {
    const corners=[[x,y],[x+1,y],[x+1,y+1],[x,y+1]];
    if(corners.some(([i,j])=>p.values[i+j*nx]===null)){omitted++;continue;}
    for(const ids of [[0,1,2],[0,2,3]]) triangles.push(ids.map(k=>{
      const [i,j]=corners[k];return {position_m:p.points_m[i][j],value:p.values[i+j*nx]};
    }));
  }
  return {triangles,omitted_cells:omitted};
}

export function replayIndex(startIndex, elapsedMs, samples, replaySeconds=12) {
  if (!Number.isInteger(startIndex) || !Number.isInteger(samples) || samples<2
      || startIndex<0 || startIndex>=samples || !Number.isFinite(elapsedMs)
      || !Number.isFinite(replaySeconds) || replaySeconds<=0) throw Error('Invalid display clock');
  // A RAF timestamp can precede a click's performance.now() within that frame.
  return Math.min(samples-1,startIndex+Math.floor(Math.max(0,elapsedMs)/(1000*replaySeconds)*(samples-1)));
}
