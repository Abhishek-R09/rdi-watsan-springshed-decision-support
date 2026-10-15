import type { AssessmentResponse } from './types';

const CATCHMENT_LABEL: Record<string, string> = {
  released: 'Provisional surface catchment', unavailable: 'Not available yet',
};

export default function ResultPanel({ response }: { response: AssessmentResponse }) {
  const payload = response.summary.payload;
  const vul = payload.vulnerability;
  const scored = typeof vul.score === 'number';
  return (
    <div className="result-panel" aria-live="polite">
      <div className="result-block">
        <p className="panel-overline">Vulnerability (Module A)</p>
        {scored ? <>
          <div className="score-row">
            <strong className="score-number">{vul.score}<span>/100</span></strong>
            <span className={`class-chip class-${(vul.class || '').toLowerCase()}`}>{vul.class}</span>
          </div>
          <p className="score-meta">
            {vul.kind === 'exposure score' ? 'Exposure score: nobody has said yet whether the flow has fallen.' : 'Vulnerability score.'}
            {' '}Confidence {vul.confidence}; {vul.coverage_pct}% of the weight had data; elevation {vul.elevation_m} m.
          </p>
          {vul.rationale && vul.rationale.length > 0 && <ul className="result-list">{vul.rationale.map((line) => <li key={line}>{line}</li>)}</ul>}
          {vul.missing_inputs && vul.missing_inputs.length > 0 && <p className="result-note">
            <strong>Would improve the answer:</strong> {vul.missing_inputs.slice(0, 3).map((m) => `${m.indicator} (${m.weight} pts)`).join('; ')}
          </p>}
          {vul.warnings && vul.warnings.length > 0 && <details className="result-more">
            <summary>Notes ({vul.warnings.length})</summary>
            <ul className="result-list">{vul.warnings.map((line) => <li key={line}>{line}</li>)}</ul>
          </details>}
          {vul.report_markdown && <details className="result-more">
            <summary>Full one-page report</summary>
            <pre className="report-text">{vul.report_markdown}</pre>
          </details>}
        </> : <p className="score-meta">{vul.status === 'not scheduled' ? 'Not requested for this run.' : `${vul.status}: ${vul.reason || ''}`}</p>}
      </div>
      <div className="result-block">
        <p className="panel-overline">Recharge zone (Module B)</p>
        <p className="score-meta"><strong>{CATCHMENT_LABEL[payload.surface_catchment_status || ''] || payload.surface_catchment_status}</strong>
          {payload.surface_catchment_reason ? `: ${payload.surface_catchment_reason}.` : ''}</p>
        <p className="score-meta">Next field check: {payload.next_field_check}</p>
      </div>
      <p className="result-run">Run {response.run_id} · saved in {response.output_directory}</p>
    </div>
  );
}
