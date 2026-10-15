import type { AgentId, AgentProgress, AgentProgressEvent } from './types';

export const PROGRESS_EVENT = 'spring-agent-progress';

export const agents: { id: AgentId; title: string; description: string; stage: string }[] = [
  { id: 'AG-ORC', title: 'Coordinate the run', description: 'Pins the request and data versions', stage: 'Prepare' },
  { id: 'AG-SPR', title: 'Check the spring', description: 'Preserves the point and field notes', stage: 'Prepare' },
  { id: 'AG-VUL', title: 'Score vulnerability', description: 'Module A score with a reason for every point', stage: 'Assess' },
  { id: 'AG-TER', title: 'Read the terrain', description: 'Checks the local elevation data', stage: 'Map' },
  { id: 'AG-CAT', title: 'Map surface drainage', description: 'Produces a candidate surface catchment', stage: 'Map' },
  { id: 'AG-GEO', title: 'Review geology', description: 'Examines rock and structural evidence', stage: 'Springshed' },
  { id: 'AG-RAI', title: 'Review rainfall', description: 'Checks historical rainfall context', stage: 'Springshed' },
  { id: 'AG-TMP', title: 'Review temperature', description: 'Only when a reviewed rule needs it', stage: 'Springshed' },
  { id: 'AG-LAS', title: 'Review land and soil', description: 'Checks infiltration context', stage: 'Springshed' },
  { id: 'AG-SHD', title: 'Assess recharge zone', description: 'Combines evidence into provisional candidates', stage: 'Springshed' },
  { id: 'AG-LIN', title: 'Trace the evidence', description: 'Links every result to inputs and rules', stage: 'Review' },
  { id: 'AG-VER', title: 'Verify the checks', description: 'Records passed, failed and unassessed checks', stage: 'Review' },
  { id: 'AG-COM', title: 'Prepare the result', description: 'Explains the outcome and its limits', stage: 'Review' },
];

export function scheduledAgents(mode: 'catchment' | 'springshed'): AgentId[] {
  return mode === 'catchment'
    ? ['AG-ORC', 'AG-SPR', 'AG-VUL', 'AG-TER', 'AG-CAT', 'AG-LIN', 'AG-VER', 'AG-COM']
    : ['AG-ORC', 'AG-SPR', 'AG-VUL', 'AG-TER', 'AG-CAT', 'AG-GEO', 'AG-RAI', 'AG-LAS', 'AG-SHD', 'AG-LIN', 'AG-VER', 'AG-COM'];
}

export function initialProgress(mode: 'catchment' | 'springshed'): Record<AgentId, AgentProgress> {
  const scheduled = new Set(scheduledAgents(mode));
  return Object.fromEntries(agents.map(({ id }) => [id, {
    status: scheduled.has(id) ? 'waiting' : 'not_scheduled',
    message: scheduled.has(id) ? 'Waiting for a run' : 'Not scheduled for this mode',
  }])) as Record<AgentId, AgentProgress>;
}

export function isProgressEvent(value: unknown): value is AgentProgressEvent {
  if (typeof value !== 'object' || value === null) return false;
  const event = value as Partial<AgentProgressEvent>;
  return typeof event.runId === 'string'
    && agents.some(({ id }) => id === event.agentId)
    && ['waiting', 'running', 'complete', 'unavailable', 'needs_review', 'not_scheduled'].includes(event.status || '')
    && typeof event.message === 'string';
}
