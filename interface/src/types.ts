export type Point = { latitude: number; longitude: number };

export type AgentStatus =
  | 'waiting'
  | 'running'
  | 'complete'
  | 'unavailable'
  | 'needs_review'
  | 'not_scheduled';

export type AgentId =
  | 'AG-ORC' | 'AG-SPR' | 'AG-TER' | 'AG-CAT'
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

export type AssessmentRequest = {
  mode: 'catchment' | 'springshed';
  spring_id: string | null;
  location: { latitude: number; longitude: number; crs: 'EPSG:4326'; accuracy_m?: number };
  field_form: {
    measurement_date_time: string | null;
    measurement_conditions: string | null;
    heavy_rainfall_recent: boolean | null;
    bucket_readings: { volume_L: number; time_s: number }[];
  };
};
