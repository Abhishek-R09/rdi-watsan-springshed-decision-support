export type Point = { latitude: number; longitude: number };

export type AgentStatus =
  | 'waiting'
  | 'running'
  | 'complete'
  | 'unavailable'
  | 'needs_review'
  | 'not_scheduled';

export type AgentId =
  | 'AG-ORC' | 'AG-SPR' | 'AG-VUL' | 'AG-TER' | 'AG-CAT'
  | 'AG-GEO' | 'AG-RAI' | 'AG-TMP' | 'AG-LAS'
  | 'AG-SHD' | 'AG-LIN' | 'AG-VER' | 'AG-COM';

export type AgentProgressEvent = {
  runId: string;
  agentId: AgentId;
  status: AgentStatus;
  message: string;
  outputId?: string;
  demo?: boolean;
};

export type AgentProgress = Pick<AgentProgressEvent, 'status' | 'message' | 'outputId' | 'demo'>;

// Module A field answers; names and allowed values match OPTIONAL in scripts/module_a_vulnerability.py.
export type VulnerabilityAnswers = Partial<Record<string, string | number>>;

export type AssessmentRequest = {
  mode: 'catchment' | 'springshed';
  spring_id: string | null;
  include_vulnerability: boolean;
  location: { latitude: number; longitude: number; crs: 'EPSG:4326'; accuracy_m?: number; elevation_m?: number };
  field_form: {
    measurement_date_time: string | null;
    measurement_conditions: string | null;
    heavy_rainfall_recent: boolean | null;
    bucket_readings: { volume_L: number; time_s: number }[];
    vulnerability_answers: VulnerabilityAnswers;
  };
};

export type VulnerabilitySummary = {
  status: string;
  reason?: string;
  score?: number;
  class?: 'Low' | 'Medium' | 'High';
  kind?: string;
  confidence?: 'Low' | 'Medium' | 'High';
  coverage_pct?: number;
  elevation_m?: number;
  rationale?: string[];
  missing_inputs?: { id: string; indicator: string; weight: number; needs: string }[];
  warnings?: string[];
  report_markdown?: string;
};

// Reply from scripts/serve_tool.py (POST /api/assess).
export type AssessmentResponse = {
  run_id: string;
  output_directory: string;
  summary: {
    status: string;
    reason: string;
    payload: {
      surface_catchment_status: string | null;
      surface_catchment_reason: string | null;
      springshed_status: string;
      area_ha: number | null;
      next_field_check: string;
      vulnerability: VulnerabilitySummary;
    };
  };
  agents: Partial<Record<AgentId, { status: AgentProgressEvent['status']; message: string; outputId?: string }>>;
};
