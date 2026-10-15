import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import MapPanel from './MapPanel';
import ResultPanel from './ResultPanel';
import { agents, initialProgress, isProgressEvent, PROGRESS_EVENT, scheduledAgents } from './progress';
import type { AgentId, AgentProgress, AssessmentRequest, AssessmentResponse, Point, VulnerabilityAnswers } from './types';
import { vulnerabilityQuestions } from './vulnerabilityQuestions';

const PREVIEW_DELAY_MS = 480;

function formatCoordinate(value: number) {
  return value.toFixed(6);
}

function statusLabel(status: AgentProgress['status'], demo?: boolean) {
  if (demo && status === 'complete') return 'Previewed';
  if (demo && status === 'running') return 'Previewing';
  if (demo && status === 'unavailable') return 'Not connected';
  return ({
    waiting: 'Waiting', running: 'In progress', complete: 'Done',
    unavailable: 'Unavailable', needs_review: 'Needs review', not_scheduled: 'Later',
  })[status];
}

function validPoint(latitude: string, longitude: string): Point | null {
  if (!latitude.trim() || !longitude.trim()) return null;
  const lat = Number(latitude);
  const lon = Number(longitude);
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180
    ? { latitude: lat, longitude: lon } : null;
}

export default function App() {
  const [mode, setMode] = useState<'catchment' | 'springshed'>('catchment');
  const [point, setPoint] = useState<Point | null>(null);
  const [pointAccuracy, setPointAccuracy] = useState<number | null>(null);
  const [latInput, setLatInput] = useState('');
  const [lonInput, setLonInput] = useState('');
  const [springName, setSpringName] = useState('');
  const [measuredAt, setMeasuredAt] = useState('');
  const [conditions, setConditions] = useState('');
  const [recentRain, setRecentRain] = useState<'unknown' | 'yes' | 'no'>('unknown');
  const [readings, setReadings] = useState([{ volume: '', seconds: '' }, { volume: '', seconds: '' }, { volume: '', seconds: '' }]);
  const [locationMessage, setLocationMessage] = useState('');
  const [progress, setProgress] = useState<Record<AgentId, AgentProgress>>(() => initialProgress('catchment'));
  const [previewing, setPreviewing] = useState(false);
  const [previewComplete, setPreviewComplete] = useState(false);
  const [preparedRequest, setPreparedRequest] = useState<AssessmentRequest | null>(null);
  const [elevationInput, setElevationInput] = useState('');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // The local Python server (scripts/serve_tool.py); without it the page falls back to the illustrative preview.
  const [backend, setBackend] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<AssessmentResponse | null>(null);
  const [runError, setRunError] = useState('');
  const runId = useRef<string | null>(null);
  const timers = useRef<number[]>([]);

  const scheduled = useMemo(() => scheduledAgents(mode), [mode]);
  const progressCount = scheduled.filter((id) => ['complete', 'unavailable', 'needs_review'].includes(progress[id].status)).length;

  const stopPreview = () => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setPreviewing(false);
  };

  function invalidatePrepared() {
    stopPreview();
    runId.current = null;
    setProgress(initialProgress(mode));
    setPreviewComplete(false);
    setPreparedRequest(null);
    setResponse(null);
    setRunError('');
  }

  useEffect(() => {
    fetch('/api/health').then((reply) => reply.ok ? reply.json() : null)
      .then((body) => setBackend(body && body.ok ? 'connected' : 'offline'))
      .catch(() => setBackend('offline'));
  }, []);

  useEffect(() => {
    const receive = (raw: Event) => {
      const detail = (raw as CustomEvent<unknown>).detail;
      if (!isProgressEvent(detail) || detail.runId !== runId.current) return;
      setProgress((current) => ({ ...current, [detail.agentId]: {
        status: detail.status, message: detail.message, outputId: detail.outputId, demo: detail.demo,
      } }));
    };
    window.addEventListener(PROGRESS_EVENT, receive);
    return () => window.removeEventListener(PROGRESS_EVENT, receive);
  }, []);

  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  function selectPoint(next: Point) {
    invalidatePrepared();
    setPoint(next);
    setPointAccuracy(null);
    setLatInput(formatCoordinate(next.latitude));
    setLonInput(formatCoordinate(next.longitude));
    setLocationMessage('');
  }

  function applyCoordinates() {
    const next = validPoint(latInput, lonInput);
    if (!next) {
      setLocationMessage('Enter a latitude from −90 to 90 and longitude from −180 to 180.');
      return;
    }
    selectPoint(next);
  }

  function editCoordinate(which: 'latitude' | 'longitude', value: string) {
    invalidatePrepared();
    setPoint(null);
    setPointAccuracy(null);
    setLocationMessage('');
    if (which === 'latitude') setLatInput(value);
    else setLonInput(value);
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setLocationMessage('This browser cannot provide your location. Enter coordinates or tap the map.');
      return;
    }
    setLocationMessage('Requesting device location…');
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        selectPoint({ latitude: coords.latitude, longitude: coords.longitude });
        setPointAccuracy(coords.accuracy);
        setLocationMessage(`Device location selected. Reported accuracy: ${Math.round(coords.accuracy)} m.`);
      },
      () => setLocationMessage('Location was unavailable. Enter coordinates or tap the map.'),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
    );
  }

  function changeMode(next: 'catchment' | 'springshed') {
    stopPreview();
    runId.current = null;
    setMode(next);
    setProgress(initialProgress(next));
    setPreviewComplete(false);
    setPreparedRequest(null);
    setResponse(null);
    setRunError('');
  }

  function createRequest(): AssessmentRequest | null {
    if (!point) {
      setLocationMessage('Choose a spring point before previewing the workflow.');
      return null;
    }
    const bucket_readings: AssessmentRequest['field_form']['bucket_readings'] = [];
    for (const [index, reading] of readings.entries()) {
      if (!reading.volume.trim() && !reading.seconds.trim()) continue;
      const volume_L = Number(reading.volume);
      const time_s = Number(reading.seconds);
      if (!Number.isFinite(volume_L) || volume_L <= 0 || !Number.isFinite(time_s) || time_s <= 0) {
        setLocationMessage(`Reading ${index + 1} needs a positive volume and time, or leave both blank.`);
        return null;
      }
      bucket_readings.push({ volume_L, time_s });
    }
    let elevation_m: number | undefined;
    if (elevationInput.trim()) {
      elevation_m = Number(elevationInput);
      if (!Number.isFinite(elevation_m) || elevation_m < -100 || elevation_m > 9000) {
        setLocationMessage('Enter the elevation in metres, or leave it blank to use the map elevation.');
        return null;
      }
    }
    const vulnerability_answers: VulnerabilityAnswers = {};
    for (const question of vulnerabilityQuestions) {
      const raw = (answers[question.id] || '').trim();
      if (!raw) continue;
      if (question.kind === 'choice') {
        vulnerability_answers[question.id] = raw;
        continue;
      }
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0 || (question.integer && !Number.isInteger(value))) {
        setLocationMessage(`${question.label}: enter ${question.integer ? 'a whole number' : 'a number'} of ${question.unit}, or leave it blank.`);
        return null;
      }
      vulnerability_answers[question.id] = value;
    }
    setLocationMessage('');
    let measurement_date_time: string | null = null;
    if (measuredAt) {
      const parsed = new Date(measuredAt);
      if (!Number.isFinite(parsed.getTime())) {
        setLocationMessage('Enter a valid measurement date and time.');
        return null;
      }
      measurement_date_time = parsed.toISOString();
    }
    return {
      mode,
      spring_id: springName.trim() || null,
      include_vulnerability: true,
      location: { ...point, crs: 'EPSG:4326', ...(pointAccuracy === null ? {} : { accuracy_m: pointAccuracy }),
        ...(elevation_m === undefined ? {} : { elevation_m }) },
      field_form: {
        measurement_date_time,
        measurement_conditions: conditions.trim() || null,
        heavy_rainfall_recent: recentRain === 'unknown' ? null : recentRain === 'yes',
        bucket_readings,
        vulnerability_answers,
      },
    };
  }

  async function runAssessment() {
    const request = createRequest();
    if (!request) return;
    stopPreview();
    setPreparedRequest(request);
    setResponse(null);
    setRunError('');
    setRunning(true);
    const id = `pending-${Date.now()}`;
    runId.current = id;
    setProgress(Object.fromEntries(Object.entries(initialProgress(mode)).map(([key, item]) => [key,
      item.status === 'waiting' ? { status: 'running', message: 'Running on this computer' } : item])) as Record<AgentId, AgentProgress>);
    try {
      const reply = await fetch('/api/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
      const body = await reply.json();
      if (runId.current !== id) return;
      if (!reply.ok) throw new Error(body.error || `The server answered ${reply.status}`);
      const result = body as AssessmentResponse;
      runId.current = result.run_id;
      setProgress(initialProgress(mode));
      for (const [agentId, item] of Object.entries(result.agents)) {
        if (!item) continue;
        window.dispatchEvent(new CustomEvent(PROGRESS_EVENT, { detail: { runId: result.run_id, agentId, ...item } }));
      }
      setResponse(result);
    } catch (error) {
      if (runId.current !== id) return;
      setProgress(initialProgress(mode));
      setRunError(error instanceof Error ? error.message : 'The assessment could not run.');
    } finally {
      setRunning(false);
    }
  }

  function previewWorkflow() {
    const request = createRequest();
    if (!request) return;
    stopPreview();
    setPreparedRequest(request);
    setPreviewComplete(false);
    setPreviewing(true);
    setProgress(initialProgress(mode));
    const id = `ui-preview-${Date.now()}`;
    runId.current = id;
    let elapsed = 0;
    scheduled.forEach((agentId, index) => {
      const unavailable = ['AG-TER', 'AG-CAT', 'AG-SHD'].includes(agentId);
      const queue = (delay: number, status: AgentProgress['status'], message: string) => {
        timers.current.push(window.setTimeout(() => {
          window.dispatchEvent(new CustomEvent(PROGRESS_EVENT, { detail: {
            runId: id, agentId, status, message, demo: true,
          } }));
        }, delay));
      };
      queue(elapsed, 'running', 'Previewing this step in the interface');
      elapsed += PREVIEW_DELAY_MS;
      queue(elapsed, unavailable ? 'unavailable' : 'complete', unavailable
        ? agentId === 'AG-SHD' ? 'Recharge rules and evidence are not connected yet'
          : 'Approved terrain inputs and routing are not connected yet'
        : 'Illustrative UI step only; no agent executed');
      if (index < scheduled.length - 1) elapsed += 110;
    });
    timers.current.push(window.setTimeout(() => {
      setPreviewing(false);
      setPreviewComplete(true);
    }, elapsed + 180));
  }

  function downloadRequest() {
    if (!preparedRequest) return;
    const file = new Blob([JSON.stringify(preparedRequest, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'spring-assessment-request.json';
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
          <div className="brand-words"><strong>Spring field desk</strong><small>RDI · WATSAN</small></div>
        </div>
        <div className={`connection-pill ${backend === 'connected' ? 'connected' : ''}`}><span className="connection-dot" />
          {backend === 'connected' ? <>Local tool connected <span className="connection-detail">· runs on this computer</span></>
            : <>Interface preview <span className="connection-detail">· {backend === 'checking' ? 'looking for the local tool' : 'local tool not running'}</span></>}</div>
      </header>

      <main>
        <section className="page-intro">
          <div>
            <p className="section-kicker">Spring assessment workspace</p>
            <h1>Start with the spring point.</h1>
            <p>Place the spring point on the map, add what you observed, and follow each agent’s evidence path.</p>
          </div>
          <div className="intro-note">
            <span className="intro-note-icon" aria-hidden="true">◎</span>
            <span>Mapped boundaries will stay provisional until checked in the field.</span>
          </div>
        </section>

        <div className="workspace-grid">
          <aside className="field-panel panel" aria-labelledby="field-heading">
            <div className="panel-heading">
              <div><p className="panel-overline">Site input</p><h2 id="field-heading">Spring details</h2></div>
              <span className="step-chip">1 of 2</span>
            </div>

            <div className="mode-switch" role="group" aria-label="Assessment mode">
              <button className={mode === 'catchment' ? 'selected' : ''} type="button" onClick={() => changeMode('catchment')}>Catchment first</button>
              <button className={mode === 'springshed' ? 'selected' : ''} type="button" onClick={() => changeMode('springshed')}>Springshed later</button>
            </div>
            <p className="mode-explanation">{mode === 'catchment'
              ? 'A surface drainage area is the first mapping step. It is not the groundwater recharge area.'
              : 'The later workflow adds geology, rainfall and land/soil evidence. Its spatial rules still need review.'}</p>

            <label className="input-label" for="spring-name">Spring name or ID <span>optional</span></label>
            <input id="spring-name" className="text-input" value={springName} onInput={(event) => { invalidatePrepared(); setSpringName(event.currentTarget.value); }} placeholder="e.g. field record ID" autoComplete="off" />

            <div className="field-divider" />
            <div className="field-row-heading"><h3>Location</h3><span>WGS84 coordinates</span></div>
            <p className="field-hint">Tap the map, enter coordinates, or use your device location.</p>
            <div className="coordinate-grid">
              <div><label className="input-label" for="latitude">Latitude</label><input id="latitude" className="text-input mono" inputMode="decimal" value={latInput} onInput={(event) => editCoordinate('latitude', event.currentTarget.value)} placeholder="e.g. 30.123456" /></div>
              <div><label className="input-label" for="longitude">Longitude</label><input id="longitude" className="text-input mono" inputMode="decimal" value={lonInput} onInput={(event) => editCoordinate('longitude', event.currentTarget.value)} placeholder="e.g. 78.123456" /></div>
            </div>
            <div className="coordinate-actions">
              <button type="button" className="small-action" onClick={applyCoordinates}>Place point</button>
              <button type="button" className="small-action quiet" onClick={useMyLocation}>Use my location</button>
            </div>
            <label className="input-label elevation-label" for="elevation">Elevation (m) <span>optional · blank uses the map</span></label>
            <input id="elevation" className="text-input mono" inputMode="decimal" value={elevationInput} onInput={(event) => { invalidatePrepared(); setElevationInput(event.currentTarget.value); }} placeholder="e.g. 1481" />
            {locationMessage && <p className="form-message" role="status">{locationMessage}</p>}
            {point && <p className="point-confirmation"><span className="point-confirmation-dot" /> Point selected · {formatCoordinate(point.latitude)}, {formatCoordinate(point.longitude)}</p>}

            <details className="field-details">
              <summary><span>Field observations</span><small>Optional for this preview</small></summary>
              <div className="details-body">
                <label className="input-label" for="measured-at">Measurement date and time</label>
                <input id="measured-at" type="datetime-local" className="text-input" value={measuredAt} onInput={(event) => { invalidatePrepared(); setMeasuredAt(event.currentTarget.value); }} />
                <label className="input-label" for="conditions">Weather and spring conditions</label>
                <textarea id="conditions" className="text-input text-area" rows={2} value={conditions} onInput={(event) => { invalidatePrepared(); setConditions(event.currentTarget.value); }} placeholder="What did you observe?" />
                <label className="input-label" for="recent-rain">Recent heavy rainfall</label>
                <select id="recent-rain" className="text-input" value={recentRain} onChange={(event) => { invalidatePrepared(); setRecentRain(event.currentTarget.value as typeof recentRain); }}>
                  <option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
                <p className="readings-heading">Bucket readings <small>Litres and seconds</small></p>
                {readings.map((reading, index) => (
                  <div className="reading-row" key={index}>
                    <span>{index + 1}</span>
                    <input aria-label={`Reading ${index + 1} volume in litres`} className="text-input" inputMode="decimal" placeholder="Volume L" value={reading.volume} onInput={(event) => { const value = event.currentTarget.value; invalidatePrepared(); setReadings((current) => current.map((item, i) => i === index ? { ...item, volume: value } : item)); }} />
                    <input aria-label={`Reading ${index + 1} time in seconds`} className="text-input" inputMode="decimal" placeholder="Time s" value={reading.seconds} onInput={(event) => { const value = event.currentTarget.value; invalidatePrepared(); setReadings((current) => current.map((item, i) => i === index ? { ...item, seconds: value } : item)); }} />
                  </div>
                ))}
              </div>
            </details>

            <details className="field-details">
              <summary><span>Vulnerability questions</span><small>Module A · all optional</small></summary>
              <div className="details-body">
                <p className="field-hint">Ask the users. The first question matters most: without it the result is only an exposure score.</p>
                {vulnerabilityQuestions.map((question) => <div key={question.id}>
                  <label className="input-label" for={`q-${question.id}`}>{question.label}{question.kind === 'number' && <span>{question.unit}</span>}</label>
                  {question.kind === 'choice'
                    ? <select id={`q-${question.id}`} className="text-input" value={answers[question.id] || ''} onChange={(event) => { const value = event.currentTarget.value; invalidatePrepared(); setAnswers((current) => ({ ...current, [question.id]: value })); }}>
                        <option value="">Not asked</option>
                        {question.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    : <input id={`q-${question.id}`} className="text-input" inputMode="decimal" value={answers[question.id] || ''} onInput={(event) => { const value = event.currentTarget.value; invalidatePrepared(); setAnswers((current) => ({ ...current, [question.id]: value })); }} placeholder={question.unit} />}
                </div>)}
              </div>
            </details>

            <div className="field-footer">
              {backend === 'connected'
                ? <button type="button" className="primary-action" onClick={runAssessment} disabled={!point || running}>
                    {running ? 'Running… the first run opens the maps' : 'Run assessment'} <span aria-hidden="true">↗</span>
                  </button>
                : <button type="button" className="primary-action" onClick={previewWorkflow} disabled={!point || previewing}>
                    {previewing ? 'Preview in progress…' : 'Preview agent progress'} <span aria-hidden="true">↗</span>
                  </button>}
              <p>{backend === 'connected' ? 'Runs on this computer; results are saved under data/03_outputs/assessments.'
                : 'The preview does not submit this form. Start scripts/serve_tool.py to run real assessments.'} Map tiles load from OpenStreetMap.</p>
            </div>
          </aside>

          <section className="map-panel panel" aria-labelledby="map-heading">
            <div className="map-panel-header">
              <div><p className="panel-overline">Location canvas</p><h2 id="map-heading">Spring map</h2></div>
              <div className="map-status"><span /> Display map only</div>
            </div>
            <MapPanel point={point} onSelect={selectPoint} />
            <div className="map-caption">
              <span>{point ? 'Selected spring point' : 'Viewing Uttarakhand · no spring selected'}</span>
              <span>{point ? `${formatCoordinate(point.latitude)}° N, ${formatCoordinate(point.longitude)}° E` : 'Click the map or enter coordinates'}</span>
            </div>
          </section>

          <aside className="progress-panel panel" aria-labelledby="progress-heading">
            <div className="panel-heading progress-heading">
              <div><p className="panel-overline">Workflow</p><h2 id="progress-heading">Agent progress</h2></div>
              <span className="step-chip">2 of 2</span>
            </div>
            {backend !== 'connected' && <div className="preview-alert"><span aria-hidden="true">◌</span><div><strong>Preview mode</strong><small>These states demonstrate the interface. No agent has run.</small></div></div>}
            <div className="progress-tally">
              <div><strong>{progressCount}<span> / {scheduled.length}</span></strong><small>steps shown</small></div>
              <div className="progress-bar" role="progressbar" aria-valuenow={progressCount} aria-valuemin={0} aria-valuemax={scheduled.length} aria-label="Workflow preview steps shown"><span style={{ width: `${scheduled.length ? progressCount / scheduled.length * 100 : 0}%` }} /></div>
            </div>
            <div className="agent-list">
              {agents.map(({ id, title, description, stage }) => {
                const item = progress[id];
                if (item.status === 'not_scheduled' && mode === 'catchment' && stage === 'Springshed') return null;
                return <div className={`agent-row status-${item.status}`} key={id}>
                  <span className="agent-node" aria-hidden="true"><span /></span>
                  <div className="agent-copy"><div className="agent-title"><strong>{title}</strong><small>{id}</small></div><p>{item.status === 'waiting' || item.status === 'not_scheduled' ? description : item.message}</p></div>
                  <span className="agent-status">{statusLabel(item.status, item.demo)}</span>
                </div>;
              })}
            </div>
            {runError && <p className="form-message" role="alert">{runError}</p>}
            {response ? <ResultPanel response={response} /> : <div className="result-empty">
              <div className="result-symbol" aria-hidden="true">⌁</div>
              <div><strong>No result yet</strong><p>{backend === 'connected'
                ? 'Run an assessment to see the vulnerability score and the recharge-zone status here.'
                : 'The interface will display results, their source trail and verification status when the local tool is running.'}</p></div>
            </div>}
            {previewComplete && <p className="preview-finished" role="status">Progress preview finished. No assessment result was calculated.</p>}
            {preparedRequest && <button type="button" className="export-action" onClick={downloadRequest}>Download prepared request JSON <span aria-hidden="true">↓</span></button>}
          </aside>
        </div>

        <footer className="page-footer">
          <span>RDI / WATSAN · Project 1 field interface</span>
          <span>Surface catchment ≠ confirmed recharge zone</span>
        </footer>
      </main>
    </div>
  );
}
