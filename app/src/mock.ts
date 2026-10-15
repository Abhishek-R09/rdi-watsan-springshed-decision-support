// Demo data used when the local tool server is not running.
// The shapes follow api.ts exactly. Numbers are illustrative, not results.
import type {
  AResult, AssessRequest, AssessResponse, BResult, CResult, DatasetSpring, DiSite, DiSiteResult, Feature,
  FeatureCollection, Health, Indicator, Range,
} from './api';
import { DEFAULT_ASSUMPTIONS } from './api';

export const DEMO_SPRING = { name: 'Nauli Dhara', latitude: 29.91903, longitude: 78.55647, elevation_m: 1481 };

export const MOCK_HEALTH: Health = { ok: true, version: 'demo', map_set: null, offline: false };

// ------------------------------------------------------------------ geometry helpers
const M_PER_DEG_LAT = 111320;
type LonLat = [number, number];

function offset(lat: number, lon: number, east: number, north: number): LonLat {
  const dLat = north / M_PER_DEG_LAT;
  const dLon = east / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  return [round6(lon + dLon), round6(lat + dLat)];
}
const round6 = (n: number) => Math.round(n * 1e6) / 1e6;

/** A wobbly ellipse whose long axis points along `bearingDeg`; the spring sits inside, near the downhill end. */
function blob(lat: number, lon: number, areaHa: number, aspect: number, bearingDeg: number, wobble: (t: number) => number): Feature {
  const a = Math.sqrt((areaHa * 10000 * aspect) / Math.PI);
  const b = a / aspect;
  const br = (bearingDeg * Math.PI) / 180;
  const ax = [Math.sin(br), Math.cos(br)]; // east, north of the long axis
  const px = [ax[1], -ax[0]];
  const cx = 0.78 * a;
  const ring: LonLat[] = [];
  for (let i = 0; i < 48; i++) {
    const t = (i / 48) * Math.PI * 2;
    const w = wobble(t);
    const u = cx + a * Math.cos(t) * w;
    const v = b * Math.sin(t) * w;
    ring.push(offset(lat, lon, u * ax[0] + v * px[0], u * ax[1] + v * px[1]));
  }
  ring.push(ring[0]);
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
}

function line(lat: number, lon: number, pts: [number, number][], properties: Record<string, any>): Feature {
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: pts.map(([e, n]) => offset(lat, lon, e, n)) }, properties };
}

const fc = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features });

/** Ray casting; ring is [lon, lat][] */
export function insidePolygon(lat: number, lon: number, f: Feature | null | undefined): boolean {
  if (!f || f.geometry?.type !== 'Polygon') return false;
  const ring: LonLat[] = f.geometry.coordinates[0];
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function distanceM(lat1: number, lon1: number, lat2: number, lon2: number) {
  const dy = (lat2 - lat1) * M_PER_DEG_LAT;
  const dx = (lon2 - lon1) * M_PER_DEG_LAT * Math.cos((lat1 * Math.PI) / 180);
  return Math.hypot(dx, dy);
}

// ------------------------------------------------------------------ overlay image (tiny gradient)
const POTENTIAL_LEGEND = [
  { label: 'Low', color: '#f2efc7' },
  { label: 'Moderate', color: '#b9dc8f' },
  { label: 'High', color: '#4fae5a' },
  { label: 'Very high', color: '#17723f' },
];

function potentialImage(): string | null {
  try {
    const size = 48;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const rgb = POTENTIAL_LEGEND.map((l) => [1, 3, 5].map((i) => parseInt(l.color.slice(i, i + 2), 16)));
    const img = ctx.createImageData(size, size);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        // highest towards the north-west, with some ridges
        const nx = x / size, ny = y / size;
        let p = 0.55 * (1 - nx) + 0.45 * (1 - ny);
        p += 0.12 * Math.sin(nx * 9 + ny * 4) + 0.08 * Math.cos(ny * 11 - nx * 3);
        p = Math.max(0, Math.min(0.999, p));
        const c = rgb[Math.floor(p * rgb.length)];
        const k = (y * size + x) * 4;
        img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2]; img.data[k + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL('image/png');
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ Module A
function moduleA(req: AssessRequest, elevation: number): AssessResponse['A'] {
  const f = req.field;
  const ind = (id: string, group: string, indicator: string, value: string, score: number, weight: number, comparison: string, why: string): Indicator => ({
    id, group, indicator, value, score, weight_used_pct: weight, points: Math.round(score * weight) / 100, comparison, why,
  });
  const indicators: Indicator[] = [
    ind('flow_vs_past', 'State (field)', 'Flow now vs 10-20 years ago', 'A bit less', 55, 12, 'Most springs in the dataset: same or a bit less', 'People report the flow has dropped a little.'),
    ind('lean_flow_lpm', 'State (field)', 'Lean-season flow', '4 L/min', 50, 12, 'Median of dataset springs: 5 L/min', 'Lean flow is close to the typical spring.'),
    ind('low_flow_months', 'State (field)', 'Months with low or no flow', '3 months', 45, 8, 'Typical: 2-4 months', 'A normal dry spell for a mid-hill spring.'),
    ind('seasonality', 'State (field)', 'Seasonality', 'Seasonal-perennial', 40, 6, '', 'Flows all year but drops a lot before the monsoon.'),
    ind('households', 'Impact (field)', 'Households using the spring', '35 households', 55, 10, 'Median: 22 households', 'More families than usual depend on it.'),
    ind('water_quality', 'Impact (field)', 'Water quality', 'Muddy after rain', 45, 6, '', 'Fast flow paths: surface water reaches the outlet quickly.'),
    ind('users_vs_past', 'Stressor (field)', 'Users now vs 10-20 years ago', 'More', 55, 7, '', 'Demand is growing.'),
    ind('disturbance_uphill', 'Stressor (field)', 'Roads, fire, grazing or landslides uphill', 'Some', 45, 8, '', 'A village road cuts the slope above the spring.'),
    ind('dry_season_rain', 'Stressor (location)', 'Dry-season rain (Nov-May)', '182 mm', 40, 9, 'Dataset range 90-310 mm', 'Average winter and pre-monsoon rain for the area.'),
    ind('slope', 'Stressor (location)', 'Slope around the spring', '24°', 25, 6, 'Dataset median 27°', 'Gentler slopes let more rain soak in.'),
    ind('protection', 'Response (field)', 'Outlet protected and an active user committee', 'One of them', 50, 8, '', 'The outlet is protected but there is no active committee.'),
    ind('recharge_works', 'Response (field)', 'Recharge works uphill', 'None', 25, 8, '', 'No trenches, pits or plantation yet: room to act.'),
  ];
  const total = indicators.reduce((s, i) => s + i.points, 0);
  const weight = indicators.reduce((s, i) => s + i.weight_used_pct, 0);
  const score = Math.round((total / weight) * 100);
  const result: AResult = {
    score,
    class: score < 35 ? 'Low' : score < 60 ? 'Medium' : 'High',
    kind: 'vulnerability score',
    coverage_pct: 86,
    indicators,
    context: [
      `Elevation used: ${elevation} m (field value; the map says ${elevation - 9} m)`,
      'Rock: Lansdowne granite / quartzite with phyllite bands (GSI 1:2M)',
      'Nearest mapped fault: 0.4 km (Main Boundary Thrust)',
      'Soil 0-30 cm (SoilGrids): clay 21%, sand 44%',
      'Yearly rain (CHIRPS 2018-2025): 1,600 mm (IMD 2001-2025: 1,540 mm)',
    ],
    nearest_dataset_spring: { record_id: 'SPR-0417', spring_name: 'Nauli Dhara', distance_m: 38 },
    elevation_gap_m: 9,
  };
  const missing = [
    { id: 'monsoon_flow_lpm', indicator: 'Monsoon flow', weight: 6, needs: 'Time how long a bucket takes to fill in August.' },
    { id: 'pollution_30m', indicator: 'Pollution sources within 30 m', weight: 5, needs: 'Walk 30 m around the outlet and count latrines, drains and cattle sheds.' },
    { id: 'spring_type', indicator: 'Spring type', needs: 'Note where the water comes out: a crack, a contact of two rocks, or a hollow.' },
  ].filter((m) => !(m.id in f) || (f as any)[m.id] === undefined || (f as any)[m.id] === '');
  return {
    module: 'A', title: 'Vulnerability assessment', version: '0.4-demo', status: 'complete', confidence: 'Medium',
    rationale: [
      `Score ${score} of 100, a Medium vulnerability: the spring is under some pressure but not in crisis.`,
      'The biggest contributors are the many households using it and the drop in flow people report.',
      'No recharge work uphill yet, which is also the clearest thing to change.',
      'Location factors (rain, slope) are close to the middle of the dataset.',
    ],
    missing_inputs: missing,
    warnings: ['Demo data: these numbers are illustrative only.', 'Lean flow was given once; one reading can be off by 30% or more.'],
    result,
    report_markdown: '',
  };
}

// ------------------------------------------------------------------ Module B
function moduleB(lat: number, lon: number, elev: number): AssessResponse['B'] {
  const w1 = (t: number) => 1 + 0.08 * Math.sin(3 * t + 0.4) + 0.05 * Math.cos(5 * t);
  const w2 = (t: number) => 1 + 0.1 * Math.sin(2 * t + 1.1) + 0.06 * Math.cos(4 * t + 0.3);
  const zones = [
    { scenario: 'small' as const, area_ha: 3.0, geojson: blob(lat, lon, 3, 1.7, 315, w1) },
    { scenario: 'likely' as const, area_ha: 6.1, geojson: blob(lat, lon, 6.1, 1.7, 315, w1) },
    { scenario: 'large' as const, area_ha: 12.2, geojson: blob(lat, lon, 12.2, 1.7, 315, w1) },
  ];
  const catchment = blob(lat, lon, 8, 2.4, 335, w2);
  const largeRing = zones[2].geojson.geometry.coordinates[0] as LonLat[];
  const lons = largeRing.map((p) => p[0]);
  const lats = largeRing.map((p) => p[1]);
  const image = potentialImage();
  const pad = 0.0006;
  const result: BResult = {
    spring_cell: { latitude: lat, longitude: lon, elevation_m: elev - 9, moved_m: 14, note: 'The spring was moved 14 m to the nearest elevation-map cell on the slope line.' },
    surface_catchment: { area_ha: 8.0, geojson: catchment },
    target_area_ha: { low: 3.0, mid: 6.1, high: 12.2, basis: 'Lean flow of 4 L/min kept up by 250-450 mm of yearly recharge, from rain of 1,600 mm.' },
    height_band_m: { min: elev, max: elev + 230 },
    zones,
    potential_overlay: image ? {
      image,
      bounds: [[Math.min(...lats) - pad, Math.min(...lons) - pad], [Math.max(...lats) + pad, Math.max(...lons) + pad]],
      legend: POTENTIAL_LEGEND,
    } : null,
    factors: [
      { id: 'rock', name: 'Rock type and cracks', weight_pct: 25, how: 'Fractured quartzite scores higher than shale or phyllite.' },
      { id: 'slope', name: 'Slope', weight_pct: 20, how: 'Gentle slopes keep water longer so more soaks in.' },
      { id: 'lineaments', name: 'Nearness to lineaments and faults', weight_pct: 20, how: 'Long straight valleys and ridges often follow cracks that carry water.' },
      { id: 'landcover', name: 'Land cover', weight_pct: 15, how: 'Forest and grass score higher than bare ground or roofs.' },
      { id: 'soil', name: 'Soil texture', weight_pct: 10, how: 'Sandy loam lets water in faster than clay.' },
      { id: 'dip', name: 'Tilt of the rock layers', weight_pct: 10, how: 'Ground uphill along the layers is favoured when the tilt is known.' },
    ],
    zone_summary: {
      mean_potential: 0.62,
      mean_slope_deg: 22,
      elevation_range_m: [elev, elev + 205],
      land_cover_pct: { 'Tree cover': 56, Cropland: 21, Grassland: 14, 'Built-up': 6, 'Bare ground': 3 },
      rock_units: ['Lansdowne granite', 'Quartzite with phyllite bands'],
      crosses_fault: true,
    },
    geology: { rock_class: 'Hard rock, fractured', unit: 'Lansdowne granite / quartzite', nearest_fault_m: 410, nearest_fault_name: 'Main Boundary Thrust' },
    faults: fc([
      line(lat, lon, [[-1600, 120], [-700, 330], [0, 410], [800, 560], [1700, 690]], { name: 'Main Boundary Thrust', type: 'thrust' }),
      line(lat, lon, [[-900, 1500], [-500, 700], [-150, -100], [200, -900]], { name: 'Unnamed fault', type: 'fault' }),
    ]),
    lineaments: fc([
      line(lat, lon, [[-700, 50], [-120, 620]], { length_m: 820 }),
      line(lat, lon, [[-420, -220], [-460, 420]], { length_m: 640 }),
      line(lat, lon, [[150, 200], [600, 900]], { length_m: 830 }),
    ]),
    streams: fc([
      line(lat, lon, [[-520, 760], [-330, 430], [-120, 150], [60, -60], [300, -330], [700, -650]], { order: 2 }),
      line(lat, lon, [[-860, 300], [-560, 230], [-330, 430]], { order: 1 }),
      line(lat, lon, [[-80, 900], [-200, 560], [-120, 150]], { order: 1 }),
      line(lat, lon, [[1300, 400], [1000, -200], [700, -650], [500, -1200]], { order: 3 }),
      line(lat, lon, [[1400, -300], [1000, -200]], { order: 1 }),
    ]),
    recharge_spots: [
      { ...pt(lat, lon, -160, 210), elevation_m: elev + 70, potential: 0.86, reason: 'Gentle bench on fractured quartzite, crossed by a lineament.' },
      { ...pt(lat, lon, -290, 150), elevation_m: elev + 95, potential: 0.81, reason: 'Grassy saddle with deep sandy-loam soil.' },
      { ...pt(lat, lon, -110, 330), elevation_m: elev + 125, potential: 0.77, reason: 'Old terraces near the fault zone: good for trenches.' },
    ],
  };
  return {
    module: 'B', title: 'Springshed and recharge zone', version: '0.3-demo', status: 'provisional', confidence: 'Low',
    rationale: [
      'The zone is drawn upslope (north-west) of the spring, where the rock layers and the slope lead water towards it.',
      'Its size comes from how much water the spring gives in the dry months and how much rain soaks in each year.',
      'A fault crosses the large zone; faults can bring water from further away, so the large zone is kept as an outer bound.',
    ],
    missing_inputs: [{ id: 'dip_direction_deg', indicator: 'Tilt of the rock layers', weight: 10, needs: 'Measure the dip direction and angle of rock layers near the outlet.' }],
    warnings: ['Demo data: these shapes are illustrative only.', 'Rock-layer tilt was not measured, so the zone shape leans on slope only.'],
    result,
    report_markdown: '',
  };
}

function pt(lat: number, lon: number, east: number, north: number) {
  const [lo, la] = offset(lat, lon, east, north);
  return { latitude: la, longitude: lo };
}

// ------------------------------------------------------------------ Module C
const MONTHLY_RAIN = [45, 50, 40, 25, 45, 190, 450, 440, 230, 55, 10, 20];

function moduleC(req: AssessRequest, lat: number, lon: number, elev: number, b: BResult): AssessResponse['C'] {
  const a = { ...DEFAULT_ASSUMPTIONS, ...(req.di.assumptions ?? {}) };
  const rain = a.annual_rain_mm ?? 1600;
  const leanFlow = req.field.lean_flow_lpm ?? 4;
  const likely = b.zones.find((z) => z.scenario === 'likely')?.geojson;
  const large = b.zones.find((z) => z.scenario === 'large')?.geojson;
  const minutesYear = 365 * 24 * 60;
  const minutesLean = a.lean_season_months * 30.4 * 24 * 60;
  const shares: Record<DiSiteResult['location_class'], Range> = {
    inside_likely: { low: 0.3, mid: 0.5, high: 0.7 },
    inside_large: { low: 0.15, mid: 0.3, high: 0.45 },
    in_catchment: { low: 0.08, mid: 0.18, high: 0.3 },
    outside: { low: 0, mid: 0.03, high: 0.08 },
    below_spring: { low: 0, mid: 0, high: 0 },
  };
  const notes: Record<DiSiteResult['location_class'], string> = {
    inside_likely: 'Inside the likely recharge zone: a good share of the water should reach the spring.',
    inside_large: 'Inside the large zone only: some water may reach the spring.',
    in_catchment: 'In the surface catchment but outside the recharge zones.',
    outside: 'Outside the recharge zones: little of this water is expected at the spring.',
    below_spring: 'Lower than the spring: water injected here cannot flow up to it.',
  };
  const scale = (r: Range, k: number): Range => ({ low: r.low * k, mid: r.mid * k, high: r.high * k });
  const sites: DiSiteResult[] = req.di.sites.map((s: DiSite, i) => {
    const d = distanceM(lat, lon, s.latitude, s.longitude);
    // pretend the ground rises north-west of the spring
    const dy = (s.latitude - lat) * M_PER_DEG_LAT;
    const dx = (s.longitude - lon) * M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
    const height = Math.round((dy - dx) * 0.35);
    let cls: DiSiteResult['location_class'] = 'outside';
    if (height < -5) cls = 'below_spring';
    else if (insidePolygon(s.latitude, s.longitude, likely)) cls = 'inside_likely';
    else if (insidePolygon(s.latitude, s.longitude, large)) cls = 'inside_large';
    else if (insidePolygon(s.latitude, s.longitude, b.surface_catchment.geojson)) cls = 'in_catchment';
    const eff = (s.first_flush ? 1 : 0.92) * (s.filter ? 1 : 0.9);
    const vol = (s.roof_area_m2 * rain) / 1000 * a.collection_coefficient * a.injection_efficiency * eff;
    const share = shares[cls];
    const flags: string[] = [];
    if (!s.first_flush) flags.push('No first-flush diverter: dirty first rain goes into the aquifer.');
    if (!s.filter) flags.push('No filter: silt may clog the handpump.');
    if (cls === 'below_spring') flags.push('Below the spring.');
    if (d > 600) flags.push('Far from the spring: slow and uncertain.');
    const mound = (sy: number) => (vol * share.mid) / (sy * Math.PI * a.radius_of_influence_m ** 2);
    return {
      id: s.id,
      name: s.name || `DI site ${i + 1}`,
      latitude: s.latitude,
      longitude: s.longitude,
      elevation_m: elev + height,
      roof_area_m2: s.roof_area_m2,
      volume_m3_per_year: Math.round(vol * 10) / 10,
      location_class: cls,
      location_note: notes[cls],
      share_reaching_spring: share,
      added_flow_lpm_annual: scale(share, (vol * 1000) / minutesYear),
      added_flow_lpm_lean: scale(share, (vol * 1000) / minutesLean),
      water_level_rise_m: { low: Math.round(mound(0.05) * 100) / 100, high: Math.round(mound(0.02) * 100) / 100 },
      travel_time_days: cls === 'below_spring' || cls === 'outside' ? null : { low: Math.round(d / 5), high: Math.round(d / 0.8) },
      distance_to_spring_m: Math.round(d),
      height_above_spring_m: height,
      flags,
    };
  });
  const sum = (k: 'added_flow_lpm_annual' | 'added_flow_lpm_lean'): Range => ({
    low: sites.reduce((t, s) => t + s[k].low, 0),
    mid: sites.reduce((t, s) => t + s[k].mid, 0),
    high: sites.reduce((t, s) => t + s[k].high, 0),
  });
  const volume = sites.reduce((t, s) => t + s.volume_m3_per_year, 0);
  const lean = sum('added_flow_lpm_lean');
  const perRoofLean = ((100 * rain) / 1000 * a.collection_coefficient * a.injection_efficiency * 1000 * 0.5) / minutesLean;
  const rainTotal = MONTHLY_RAIN.reduce((s, v) => s + v, 0);
  const result: CResult = {
    rain: { annual_mm: rain, source: a.annual_rain_mm == null ? 'CHIRPS 2018-2025 mean at the spring' : 'Entered by you', monthly_mm: MONTHLY_RAIN.map((v) => Math.round((v * rain) / rainTotal)) },
    sites,
    totals: {
      volume_m3_per_year: Math.round(volume * 10) / 10,
      added_flow_lpm_annual: sum('added_flow_lpm_annual'),
      added_flow_lpm_lean: lean,
      lean_flow_lpm: leanFlow,
      pct_of_lean_flow: leanFlow > 0 ? scale(lean, 100 / leanFlow) : null,
    },
    monthly_injection_m3: sites.length ? MONTHLY_RAIN.map((v) => Math.round((v / rainTotal) * volume * 10) / 10) : null,
    roofs_for_10pct: leanFlow > 0 ? Math.ceil((0.1 * leanFlow) / perRoofLean) : null,
    assumptions: [
      { id: 'annual_rain_mm', label: 'Yearly rain', value: rain, unit: 'mm', note: a.annual_rain_mm == null ? 'From rainfall maps at the spring' : 'Entered by you' },
      { id: 'collection_coefficient', label: 'Share of roof rain reaching the handpump', value: a.collection_coefficient, unit: '', note: 'Losses from splashing, gutters and evaporation' },
      { id: 'injection_efficiency', label: 'Share left after first flush and overflow', value: a.injection_efficiency, unit: '', note: 'Heavy storms overflow the pipe' },
      { id: 'lean_season_months', label: 'Months the extra water comes out in', value: a.lean_season_months, unit: 'months', note: 'Best case: all of it in the dry season' },
      { id: 'radius_of_influence_m', label: 'Radius of the water mound', value: a.radius_of_influence_m, unit: 'm', note: 'Used for the water-level rise' },
      { id: 'specific_yield', label: 'Share of rock that holds water', value: '0.02-0.05', unit: '', note: 'Fractured hard rock' },
    ],
    benchmarks: [
      'A 100 m² roof in 1,600 mm of rain catches about 160 m³ (1.6 lakh litres) a year before losses.',
      'Roof-water recharge pilots in the Himalaya report 5-20% more lean flow after 2-3 years.',
      'Springs in the dataset give a median lean flow of 5 L/min.',
    ],
    monitoring_plan: [
      'Measure the spring flow with a bucket and stopwatch on the 1st of every month, starting now, before any work.',
      'Keep the same record for one nearby spring that gets no recharge work, to compare.',
      'Note rain on the day of each reading and any cleaning of first-flush diverters and filters.',
      'Check water in the DI handpumps once a month after the monsoon (a dip-meter or a rope with a weight).',
      'Compare May-June flows over at least two years before judging the result.',
    ],
  };
  return {
    module: 'C', title: 'Potential impact of DI recharging', version: '0.2-demo', status: sites.length ? 'provisional' : 'complete',
    confidence: 'Low',
    rationale: sites.length ? [
      `${sites.length} DI site${sites.length > 1 ? 's' : ''} could put about ${Math.round(volume)} m³ of roof water into the ground each year.`,
      'Only part of it reaches this spring; the share depends on whether the handpump sits inside the recharge zone.',
      'The added flow is a best case: it assumes the extra water comes out evenly in the dry months.',
    ] : ['No DI sites were given. Add handpumps on the map to see how much water they could add.'],
    missing_inputs: [],
    warnings: ['Demo data: these numbers are illustrative only.', 'Check each handpump is truly defunct and its bore is open before planning.'],
    result,
    report_markdown: '',
  };
}

// ------------------------------------------------------------------ public
export function mockAssess(req: AssessRequest): AssessResponse {
  const { latitude: lat, longitude: lon } = req.spring;
  const elev = Math.round(req.spring.elevation_m ?? DEMO_SPRING.elevation_m);
  const B = moduleB(lat, lon, elev);
  return {
    run_id: `demo-${Date.now().toString(36)}`,
    created_at: new Date().toISOString(),
    map_set: 'none approved',
    spring: { name: req.spring.name || 'Unnamed spring', latitude: lat, longitude: lon, elevation_m: elev },
    A: moduleA(req, elev),
    B,
    C: moduleC(req, lat, lon, elev, B.result!),
  };
}

/** Two example DI sites for the demo spring: one inside the likely zone, one further out. */
export function demoDiSites(): DiSite[] {
  const { latitude: lat, longitude: lon } = DEMO_SPRING;
  const a = pt(lat, lon, -95, 120);
  const b = pt(lat, lon, -260, 360);
  return [
    { id: 'di-demo-1', name: 'School handpump', ...a, roof_area_m2: 180, first_flush: true, filter: true },
    { id: 'di-demo-2', name: 'Panchayat bhawan', ...b, roof_area_m2: 120, first_flush: true, filter: false },
  ];
}

/** A ready-made answer for the demo spring, with two DI sites. */
export const mockResponse = (): AssessResponse => mockAssess({
  spring: DEMO_SPRING,
  field: { flow_vs_past: 'a_bit_less', lean_flow_lpm: 4, low_flow_months: 3, households: 35, seasonality: 'seasonal_perennial' },
  di: { sites: demoDiSites(), assumptions: { annual_rain_mm: 1600 } },
});

// ------------------------------------------------------------------ spring list
const NAMES = [
  'Bhatwari Dhara', 'Kaflani Naula', 'Gadhera Srot', 'Chandi Dhara', 'Mala Naula', 'Pipal Pani', 'Thala Dhara',
  'Banj Naula', 'Kholi Dhara', 'Sera Srot', 'Gaon Dhara', 'Devi Naula', 'Ghatti Pani', 'Upli Dhara', 'Bagar Naula',
  'Simli Dhara', 'Kunj Srot', 'Hariyali Pani', 'Talla Naula', 'Malla Dhara', 'Jamun Dhara', 'Chir Naula', 'Patal Pani',
  'Gwar Dhara', 'Dungri Naula', 'Bakhli Srot', 'Kapkot Dhara', 'Ranikhet Naula', 'Saknoli Dhara',
];
const VILLAGES = ['Bhatwari', 'Kaflani', 'Thalisain', 'Chandpur', 'Malari', 'Pipalkoti', 'Thal', 'Banjgaon', 'Kholi', 'Seraghat',
  'Gaon', 'Devidhura', 'Ghat', 'Upli', 'Bagar', 'Simli', 'Kunjapuri', 'Hariyali', 'Talla Ramgarh', 'Malla Ramgarh',
  'Jamunda', 'Chirbatiya', 'Patalbhuvaneshwar', 'Gwaldam', 'Dungri', 'Bakhli', 'Kapkot', 'Ranikhet', 'Saknoli'];
const DISTRICTS: [string, number, number][] = [
  ['Uttarkashi', 30.75, 78.4], ['Tehri Garhwal', 30.35, 78.45], ['Dehradun', 30.45, 77.95], ['Pauri Garhwal', 29.95, 78.75],
  ['Rudraprayag', 30.4, 79.05], ['Chamoli', 30.35, 79.45], ['Almora', 29.65, 79.6], ['Nainital', 29.35, 79.45],
  ['Bageshwar', 29.9, 79.75], ['Champawat', 29.3, 79.95], ['Pithoragarh', 29.65, 79.95],
];

export function mockSprings(): DatasetSpring[] {
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const list: DatasetSpring[] = [{
    id: 'SPR-0417', name: DEMO_SPRING.name, village: 'Nauli', district: 'Pauri Garhwal',
    latitude: DEMO_SPRING.latitude, longitude: DEMO_SPRING.longitude, elevation_m: DEMO_SPRING.elevation_m, source: 'Demo list',
  }];
  NAMES.forEach((name, i) => {
    const [district, dlat, dlon] = DISTRICTS[i % DISTRICTS.length];
    const lat = Math.min(30.9, Math.max(29.2, dlat + (rand() - 0.5) * 0.4));
    const lon = Math.min(80.0, Math.max(77.8, dlon + (rand() - 0.5) * 0.4));
    list.push({
      id: `SPR-${String(500 + i * 13).padStart(4, '0')}`, name, village: VILLAGES[i], district,
      latitude: round6(lat), longitude: round6(lon), elevation_m: Math.round(900 + rand() * 1500), source: 'Demo list',
    });
  });
  return list;
}
