/** Rendering-only helpers. No field law, force law, integrator or interpolation. */
export function validateSnapshot(d) {
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const vec = v => Array.isArray(v) && v.length === 3 && v.every(finite);
  if (d?.visualization_version !== 1 || typeof d.title !== 'string') throw Error('Unsupported visualization snapshot');
  if (!Array.isArray(d.bounds_m) || d.bounds_m.length !== 6 || !d.bounds_m.every(finite)
      || [0,2,4].some(i => d.bounds_m[i] >= d.bounds_m[i+1])) throw Error('Invalid bounds');
  if (d.units?.position !== 'm' || d.units?.time !== 's') throw Error('Only SI metre/second snapshots supported');
  if (!(d.units.field === 'N/C' && d.units.potential === 'V')
      && !(d.units.field === 'm/s²' && d.units.potential === 'J/kg')) throw Error('Unsupported physical units');
  if (!Number.isInteger(d.animation?.samples) || d.animation.samples < 2
      || !finite(d.animation.duration_s) || d.animation.duration_s <= 0
      || d.animation.role !== 'saved_trajectory_sample_display_only') throw Error('Invalid saved timeline');
  if (!Array.isArray(d.geometry) || d.geometry.some(g => !vec(g.center_m)
      || !['point','sphere','shell','line','plane','none'].includes(g.shape))) throw Error('Unsupported source geometry');
  for (const g of d.geometry) {
    if (['sphere','shell'].includes(g.shape) && (!finite(g.radius_m) || g.radius_m <= 0)) throw Error('Invalid radius');
    if (['line','plane'].includes(g.shape) && (!vec(g.direction)
        || !finite(g.display_span_m) || g.display_span_m <= 0)) throw Error('Invalid infinite-source patch');
  }
  if (!Array.isArray(d.trajectories) || d.trajectories.some(t =>
      t.role !== 'calculated_test_particle_trajectory_not_field_line'
      || !Array.isArray(t.positions_m) || t.positions_m.length !== d.animation.samples
      || !t.positions_m.every(vec) || !finite(t.marker_radius_m) || t.marker_radius_m <= 0)) throw Error('Invalid saved trajectory');
  const a = d.field?.schematic_arrows;
  if (d.field?.unit !== d.units.field || d.field.role !== 'schematic_field_direction_glyphs_not_field_lines'
      || !a || a.not_calibrated_field_lines !== true || !finite(a.display_length_m) || a.display_length_m <= 0
      || !Array.isArray(a.origins_m) || !Array.isArray(a.unit_directions)
      || a.origins_m.length !== a.unit_directions.length || !a.origins_m.every(vec)
      || !a.unit_directions.every(v => vec(v) && Math.abs(Math.hypot(...v)-1) < 1e-12)) throw Error('Invalid schematic field arrows');
  const p = d.potential, nx = p?.points_m?.length, ny = p?.points_m?.[0]?.length;
  if (p?.unit !== d.units.potential || p.sample_order !== 'x_fastest_fortran'
      || !Array.isArray(p.points_m) || nx < 2 || ny < 2
      || !p.points_m.every(row => Array.isArray(row) && row.length === ny && row.every(vec))
      || !Array.isArray(p.values) || p.values.length !== nx*ny
      || !p.values.every(v => v === null || finite(v))) throw Error('Invalid potential slice');
  if (!Array.isArray(d.annotations) || d.annotations.some(a => typeof a.text !== 'string')
      || !Array.isArray(d.missing_geometry) || d.missing_geometry.some(s => typeof s !== 'string')) throw Error('Invalid annotations');
  return d;
}

export function displayTransform(d) {
  const b=d.bounds_m;
  return {origin_m:[(b[0]+b[1])/2,(b[2]+b[3])/2,(b[4]+b[5])/2],
          scale_m:Math.max(b[1]-b[0],b[3]-b[2],b[5]-b[4])};
}
export const toDisplay = (v,t) => v.map((x,i)=>(x-t.origin_m[i])/t.scale_m);
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
