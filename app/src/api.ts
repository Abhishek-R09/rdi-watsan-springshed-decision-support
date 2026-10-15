// What the page sends to and gets back from the local server (scripts/spring_tool_server.py).
// The Python side builds exactly these shapes; change both together.

export type Status = 'complete' | 'provisional' | 'unavailable' | 'failed';
export type Confidence = 'Low' | 'Medium' | 'High';
export type Range = { low: number; mid: number; high: number };
export type Feature = { type: 'Feature'; geometry: any; properties: Record<string, any> };
export type FeatureCollection = { type: 'FeatureCollection'; features: Feature[] };

// ------------------------------------------------------------------ request
export type FieldAnswers = {
  // Module A questions (ids and allowed values match OPTIONAL in scripts/module_a_vulnerability.py)
  flow_vs_past?: 'more' | 'same' | 'a_bit_less' | 'much_less' | 'dries_at_times';
  lean_flow_lpm?: number;
  monsoon_flow_lpm?: number;
  low_flow_months?: number;
  households?: number;
  users_vs_past?: 'fewer' | 'same' | 'more' | 'much_more';
  water_quality?: 'no_issue' | 'muddy_after_rain' | 'contamination';
  pollution_30m?: 'none' | 'one' | 'two_or_more' | 'latrine';
  disturbance_uphill?: 'little' | 'some' | 'major';
  protection?: 'both' | 'one' | 'neither';
  recharge_works?: 'maintained' | 'neglected' | 'none';
  seasonality?: 'perennial' | 'seasonal_perennial' | 'seasonal' | 'highly_seasonal' | 'ephemeral';
  spring_type?: string;
  rock_at_outlet?: string;
  // Module B extras
  dip_direction_deg?: number; // direction the rock layers tilt down towards, 0-360 from north
  dip_angle_deg?: number;
};

export type DiSite = {
  id: string;
  name?: string;
  latitude: number;
  longitude: number;
  roof_area_m2: number;
  first_flush: boolean;
  filter: boolean;
};

export type DiAssumptions = {
  annual_rain_mm: number | null; // null = read from the rainfall maps at the spring
  collection_coefficient: number; // share of roof rain that reaches the handpump (0.7-0.9)
  injection_efficiency: number; // share left after first flush and overflow (0.7-0.95)
  lean_season_months: number; // months the extra water is assumed to come out in (best case)
  radius_of_influence_m: number; // mound radius for the water-level estimate
};

export type AssessRequest = {
  spring: { name?: string; latitude: number; longitude: number; elevation_m?: number | null };
  field: FieldAnswers;
  di: { sites: DiSite[]; assumptions?: Partial<DiAssumptions> };
};

// ------------------------------------------------------------------ response
export type MissingInput = { id: string; indicator: string; weight?: number; needs: string };

export type ModuleOutput<R> = {
  module: 'A' | 'B' | 'C';
  title: string;
  version: string;
  status: Status;
  confidence: Confidence;
  rationale: string[];
  missing_inputs: MissingInput[];
  warnings: string[];
  result: R | null;
  report_markdown: string;
};

export type Indicator = {
  id: string;
  group: string; // e.g. 'State (field)', 'Stressor (location)'
  indicator: string;
  value: string;
  score: number; // 0-100
  weight_used_pct: number;
  points: number;
  comparison: string;
  why: string;
};

export type AResult = {
  score: number;
  class: 'Low' | 'Medium' | 'High';
  kind: 'vulnerability score' | 'exposure score';
  coverage_pct: number;
  indicators: Indicator[];
  context: string[];
  nearest_dataset_spring: { record_id: string; spring_name: string; distance_m: number } | null;
  elevation_gap_m: number | null;
};

export type Zone = {
  scenario: 'small' | 'likely' | 'large';
  area_ha: number;
  geojson: Feature; // Polygon or MultiPolygon, WGS84
};

export type BResult = {
  spring_cell: { latitude: number; longitude: number; elevation_m: number; moved_m: number; note: string };
  surface_catchment: { area_ha: number; geojson: Feature | null };
  target_area_ha: Range & { basis: string };
  height_band_m: { min: number; max: number }; // elevations above sea level the zone may use
  zones: Zone[]; // nested: small inside likely inside large
  potential_overlay: {
    image: string; // data:image/png;base64,...
    bounds: [[number, number], [number, number]]; // [[south, west], [north, east]]
    legend: { label: string; color: string }[];
  } | null;
  factors: { id: string; name: string; weight_pct: number; how: string }[];
  zone_summary: {
    mean_potential: number; // 0-1
    mean_slope_deg: number;
    elevation_range_m: [number, number];
    land_cover_pct: Record<string, number>;
    rock_units: string[];
    crosses_fault: boolean;
  } | null;
  geology: { rock_class: string; unit: string; nearest_fault_m: number | null; nearest_fault_name: string } | null;
  faults: FeatureCollection; // GSI faults and thrusts in the window (properties.name, properties.type)
  lineaments: FeatureCollection; // DEM lineament candidates in the window
  streams: FeatureCollection; // DEM streams in the window (properties.order)
  recharge_spots: { latitude: number; longitude: number; elevation_m: number; potential: number; reason: string }[];
};

export type DiSiteResult = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  elevation_m: number | null;
  roof_area_m2: number;
  volume_m3_per_year: number;
  location_class: 'inside_likely' | 'inside_large' | 'in_catchment' | 'outside' | 'below_spring';
  location_note: string;
  share_reaching_spring: Range;
  added_flow_lpm_annual: Range;
  added_flow_lpm_lean: Range;
  water_level_rise_m: { low: number; high: number };
  travel_time_days: { low: number; high: number } | null;
  distance_to_spring_m: number;
  height_above_spring_m: number | null;
  flags: string[];
};

export type CResult = {
  rain: { annual_mm: number; source: string; monthly_mm: number[] | null }; // monthly: Jan..Dec
  sites: DiSiteResult[];
  totals: {
    volume_m3_per_year: number;
    added_flow_lpm_annual: Range;
    added_flow_lpm_lean: Range;
    lean_flow_lpm: number | null;
    pct_of_lean_flow: Range | null;
  };
  monthly_injection_m3: number[] | null; // Jan..Dec, all sites
  roofs_for_10pct: number | null; // 100 m2 roofs inside the likely zone needed for +10% lean flow (mid case)
  assumptions: { id: string; label: string; value: number | string; unit: string; note: string }[];
  benchmarks: string[];
  monitoring_plan: string[];
};

export type AssessResponse = {
  run_id: string;
  created_at: string;
  map_set: string; // approved map set id, or 'none approved'
  spring: { name: string; latitude: number; longitude: number; elevation_m: number };
  A: ModuleOutput<AResult>;
  B: ModuleOutput<BResult>;
  C: ModuleOutput<CResult>;
};

export type DatasetSpring = {
  id: string;
  name: string;
  village: string;
  district: string;
  latitude: number;
  longitude: number;
  elevation_m: number | null;
  source: string;
};

export type Health = {
  ok: boolean;
  version: string;
  map_set: { snapshot_id: string; approved_by: string; approved_at: string } | null;
  offline: boolean; // true when only the approved map set is read (nothing downloaded)
};

export const DEFAULT_ASSUMPTIONS: DiAssumptions = {
  annual_rain_mm: null,
  collection_coefficient: 0.8,
  injection_efficiency: 0.85,
  lean_season_months: 5,
  radius_of_influence_m: 50,
};

export async function getHealth(): Promise<Health> {
  const r = await fetch('/api/health');
  if (!r.ok) throw new Error(`Server answered ${r.status}`);
  return r.json();
}

export async function getSprings(): Promise<DatasetSpring[]> {
  const r = await fetch('/api/springs');
  if (!r.ok) throw new Error(`Server answered ${r.status}`);
  return r.json();
}

export async function assess(request: AssessRequest): Promise<AssessResponse> {
  const r = await fetch('/api/assess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Server answered ${r.status}`);
  return body;
}
