import type { ReactNode } from 'react';
import type { AResult, AssessResponse, BResult, CResult, Feature, Indicator, ModuleOutput } from '../api';
import { MONTHS, classColor, flow, litres, locationClass, num, pct, range, scoreColor, statusLabel } from '../format';
import { Gauge, MonthlyBars, RangeStrip, StackedBar } from './charts';
import type { Tab } from './MapView';

type Props = {
  result: AssessResponse;
  tab: Tab;
  setTab: (t: Tab) => void;
  stale: boolean;
  onFocus: (lat: number, lon: number, zoom?: number) => void;
  onAddSite: () => void;
};

const TABS: { id: Tab; label: string; key: 'A' | 'B' | 'C' }[] = [
  { id: 'A', label: 'Vulnerability', key: 'A' },
  { id: 'B', label: 'Springshed', key: 'B' },
  { id: 'C', label: 'DI impact', key: 'C' },
];

export default function Results({ result, tab, setTab, stale, onFocus, onAddSite }: Props) {
  return (
    <div className="results">
      <div className="results-head">
        <div>
          <h2 className="results-title">{result.spring.name}</h2>
          <p className="muted small">
            {result.spring.latitude.toFixed(5)}, {result.spring.longitude.toFixed(5)} · {num(result.spring.elevation_m)} m ·
            {' '}{new Date(result.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
          </p>
        </div>
      </div>
      {stale && <p className="msg msg-info">You changed the inputs since this result. Press <b>Assess this spring</b> again to update it.</p>}
      <div className="tabs" role="tablist" aria-label="Results">
        {TABS.map((t) => {
          const m = result[t.key];
          return (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`}
              className={`tab${tab === t.id ? ' on' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
              {m.status === 'provisional' && <span className="dot dot-amber" title="Provisional" />}
              {(m.status === 'unavailable' || m.status === 'failed') && <span className="dot dot-grey" title={statusLabel[m.status]} />}
            </button>
          );
        })}
      </div>
      <div className="tab-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'A' && <ModuleFrame m={result.A}>{(r) => <VulnerabilityTab m={result.A} r={r} />}</ModuleFrame>}
        {tab === 'B' && <ModuleFrame m={result.B}>{(r) => <SpringshedTab m={result.B} r={r} onFocus={onFocus} />}</ModuleFrame>}
        {tab === 'C' && <ModuleFrame m={result.C}>{(r) => <DiTab m={result.C} r={r} onAddSite={onAddSite} />}</ModuleFrame>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ shared pieces
function ModuleFrame<R>({ m, children }: { m: ModuleOutput<R>; children: (r: R) => ReactNode }) {
  const broken = m.status === 'unavailable' || m.status === 'failed' || m.result == null;
  return (
    <div className="module">
      <div className="module-head">
        <h3>{m.title}</h3>
        <span className={`badge badge-${m.status}`}>{statusLabel[m.status]}</span>
        {!broken && <span className="badge badge-conf">Confidence: {m.confidence}</span>}
      </div>
      {m.status === 'provisional' && !broken && (
        <p className="msg msg-amber small">Provisional: a first answer. Some inputs or checks are still missing.</p>
      )}
      {broken ? (
        <div className="unavailable">
          <p className="unavailable-title">{m.status === 'failed' ? 'This part could not run.' : 'This part has no answer for this spring yet.'}</p>
          {m.rationale.length > 0 && <ul>{m.rationale.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          {m.warnings.length > 0 && <ul className="warn-list">{m.warnings.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          {m.missing_inputs.length > 0 && <MissingList m={m} />}
        </div>
      ) : children(m.result as R)}
    </div>
  );
}

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="block">
      <h4>{title}</h4>
      <ul className="bullets">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </section>
  );
}

function Warnings({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <details className="warnings block">
      <summary>Notes and warnings ({items.length})</summary>
      <ul className="warn-list">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </details>
  );
}

function MissingList<R>({ m }: { m: ModuleOutput<R> }) {
  const items = [...m.missing_inputs].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)).slice(0, 5);
  if (!items.length) return null;
  return (
    <section className="block">
      <h4>What would improve this answer</h4>
      <ul className="improve">
        {items.map((x) => (
          <li key={x.id}>
            <b>{x.indicator}</b>{x.weight ? <span className="muted"> · worth {num(x.weight)}% of the score</span> : null}
            <div>{x.needs}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Stat({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string }) {
  return (
    <div className="stat" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ A
function VulnerabilityTab({ m, r }: { m: ModuleOutput<AResult>; r: AResult }) {
  const groups = new Map<string, Indicator[]>();
  for (const i of r.indicators) groups.set(i.group, [...(groups.get(i.group) ?? []), i]);
  return (
    <>
      <div className="hero">
        <Gauge score={r.score} label={r.class} />
        <div className="hero-text">
          <div className="hero-class" style={{ color: classColor(r.class) }}>{r.class} {r.kind === 'exposure score' ? 'exposure' : 'vulnerability'}</div>
          <p className="small">
            {r.kind === 'exposure score'
              ? 'This is an exposure score: it is built only from the maps (rain, slope, land use) because no field answers were given. It says how exposed the place is, not how the spring itself is doing.'
              : 'Higher = more at risk of drying up or getting dirty. It combines your field answers with what the maps say about the place.'}
          </p>
          <div className="meta-row">
            <span><b>{m.confidence}</b> confidence</span>
            <span><b>{num(r.coverage_pct)}%</b> of the score has data</span>
          </div>
          <div className="coverage" aria-hidden="true"><span style={{ width: `${Math.min(100, r.coverage_pct)}%` }} /></div>
        </div>
      </div>
      <Bullets title="Why this score" items={m.rationale} />
      <MissingList m={m} />
      <section className="block">
        <h4>What makes up the score</h4>
        <p className="hint">Each bar is how worrying that sign is (0–100). Points = its share of the final score.</p>
        {[...groups.entries()].map(([g, list]) => (
          <div className="ind-group" key={g}>
            <div className="ind-group-head">
              <span>{g}</span>
              <span className="muted">{num(list.reduce((s, i) => s + i.points, 0), 1)} pts</span>
            </div>
            {list.map((i) => (
              <div className="ind" key={i.id} title={i.why}>
                <div className="ind-top">
                  <span className="ind-name">{i.indicator}</span>
                  <span className="ind-pts">+{num(i.points, 1)}</span>
                </div>
                <div className="ind-bar-row">
                  <div className="ind-bar"><span style={{ width: `${i.score}%`, background: scoreColor(i.score) }} /></div>
                  <span className="ind-val">{i.value}</span>
                </div>
                <div className="ind-why">{i.why}{i.comparison ? <span className="muted"> · {i.comparison}</span> : null}</div>
              </div>
            ))}
          </div>
        ))}
      </section>
      {(r.context.length > 0 || r.nearest_dataset_spring) && (
        <section className="block">
          <h4>About the place</h4>
          <ul className="bullets muted-bullets">
            {r.nearest_dataset_spring && (
              <li>Nearest spring in the dataset: {r.nearest_dataset_spring.spring_name} ({r.nearest_dataset_spring.record_id}), {num(r.nearest_dataset_spring.distance_m)} m away</li>
            )}
            {r.elevation_gap_m != null && Math.abs(r.elevation_gap_m) >= 1 && <li>Your elevation and the map elevation differ by {num(Math.abs(r.elevation_gap_m))} m</li>}
            {r.context.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </section>
      )}
      <Warnings items={m.warnings} />
    </>
  );
}

// ------------------------------------------------------------------ B
function SpringshedTab({ m, r, onFocus }: { m: ModuleOutput<BResult>; r: BResult; onFocus: Props['onFocus'] }) {
  const likely = r.zones.find((z) => z.scenario === 'likely');
  const small = r.zones.find((z) => z.scenario === 'small');
  const large = r.zones.find((z) => z.scenario === 'large');
  const zs = r.zone_summary;
  return (
    <>
      <p className="msg msg-caution">A first estimate from maps. Walk the springshed with a geologist before spending money.</p>
      <div className="stats">
        <Stat label="Likely springshed area" accent="var(--green)"
          value={<>{num(likely?.area_ha ?? r.target_area_ha.mid, 1)} <small>ha</small></>}
          sub={`Could be ${num(small?.area_ha ?? r.target_area_ha.low, 1)} – ${num(large?.area_ha ?? r.target_area_ha.high, 1)} ha`} />
        <Stat label="Surface catchment" accent="var(--water)"
          value={r.surface_catchment.geojson || r.surface_catchment.area_ha ? <>{num(r.surface_catchment.area_ha, 1)} <small>ha</small></> : '–'}
          sub="Where rain runs off towards the spring" />
        <Stat label="Height band" accent="var(--earth)"
          value={<>{num(r.height_band_m.min)}–{num(r.height_band_m.max)} <small>m</small></>}
          sub="Heights the springshed may use" />
      </div>
      <p className="small"><b>How big it should be:</b> {r.target_area_ha.basis}</p>
      {r.spring_cell.moved_m > 0 && <p className="hint">{r.spring_cell.note}</p>}

      {zs && (
        <section className="block">
          <h4>Inside the likely springshed</h4>
          <StackedBar shares={zs.land_cover_pct} />
          <dl className="facts">
            <div><dt>Mean slope</dt><dd>{num(zs.mean_slope_deg)}°</dd></div>
            <div><dt>Recharge potential</dt><dd>{Math.round(zs.mean_potential * 100)}%</dd></div>
            <div><dt>Heights</dt><dd>{num(zs.elevation_range_m[0])}–{num(zs.elevation_range_m[1])} m</dd></div>
            <div><dt>Crosses a fault</dt><dd>{zs.crosses_fault ? 'Yes' : 'No'}</dd></div>
            {zs.outside_catchment_pct != null && <div><dt>Outside the surface catchment</dt><dd>{zs.outside_catchment_pct}%</dd></div>}
            {zs.soil && <div className="wide"><dt>Soil (top 30 cm)</dt><dd>{zs.soil.class}: clay {num(zs.soil.clay_pct)}%, sand {num(zs.soil.sand_pct)}%</dd></div>}
            <div className="wide"><dt>Rock</dt><dd>{zs.rock_units.join(', ') || '–'}</dd></div>
          </dl>
        </section>
      )}
      {r.geology && (
        <p className="small">
          <b>Rock at the spring:</b> {r.geology.unit} ({r.geology.rock_class.toLowerCase()})
          {r.geology.nearest_fault_m != null && <>. Nearest mapped fault: {num(r.geology.nearest_fault_m)} m ({r.geology.nearest_fault_name})</>}.
        </p>
      )}

      {r.detached && <BeyondRidge d={r.detached} onFocus={onFocus} />}

      {r.recharge_spots.length > 0 && (
        <section className="block">
          <h4>Suggested recharge spots</h4>
          <p className="hint">Good places for trenches, pits or planting. Click one to see it on the map.</p>
          <ol className="spots">
            {r.recharge_spots.map((s, i) => (
              <li key={i}>
                <button type="button" onClick={() => onFocus(s.latitude, s.longitude, 17)}>
                  <span className="spot-num">★ {i + 1}</span>
                  <span className="spot-body">
                    <span>{s.reason}</span>
                    <span className="muted small">{num(s.elevation_m)} m · potential {Math.round(s.potential * 100)}%</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      {r.factors.length > 0 && (
        <section className="block">
          <h4>What the recharge map looks at</h4>
          <ul className="factors">
            {r.factors.map((f) => (
              <li key={f.id}>
                <div className="factor-top"><span>{f.name}</span><b>{num(f.weight_pct)}%</b></div>
                <div className="factor-bar"><span style={{ width: `${f.weight_pct}%` }} /></div>
                <div className="hint">{f.how}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Bullets title="How the springshed was drawn" items={m.rationale} />
      <MissingList m={m} />
      <Warnings items={m.warnings} />
    </>
  );
}

/** Middle of a polygon's outline, for flying the map to it. */
function middleOf(f: Feature | null): [number, number] | null {
  let w = Infinity, so = Infinity, e = -Infinity, n = -Infinity;
  const add = (c: any) => {
    if (typeof c[0] === 'number') { w = Math.min(w, c[0]); e = Math.max(e, c[0]); so = Math.min(so, c[1]); n = Math.max(n, c[1]); }
    else for (const x of c) add(x);
  };
  if (f?.geometry?.coordinates) add(f.geometry.coordinates);
  return Number.isFinite(w) ? [(so + n) / 2, (w + e) / 2] : null;
}

function BeyondRidge({ d, onFocus }: { d: NonNullable<BResult['detached']>; onFocus: Props['onFocus'] }) {
  return (
    <section className="block beyond">
      <h4>Recharge areas beyond the ridge</h4>
      <p className="small">{d.reason}</p>
      {d.candidates.length > 0 ? (
        <>
          <p className="hint">These are possibilities to check, not findings. Click one to see it on the map (purple, dashed).</p>
          <ol className="spots">
            {d.candidates.map((c) => {
              const mid = middleOf(c.geojson);
              return (
                <li key={c.id}>
                  <button type="button" onClick={() => mid && onFocus(mid[0], mid[1], 15)} disabled={!mid}>
                    <span className="spot-num beyond-num">{c.id}</span>
                    <span className="spot-body">
                      <span>{c.why}</span>
                      {c.rock_unit && <span className="muted small">Rock: {c.rock_unit}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </>
      ) : (
        <p className="hint">None found. {d.searched}</p>
      )}
      {d.candidates.length > 0 && <p className="hint">{d.searched}</p>}
      {d.candidates.length > 0 && d.checks.length > 0 && (
        <details className="checks">
          <summary>How to check one in the field</summary>
          <ul>{d.checks.map((x) => <li key={x}>{x}</li>)}</ul>
        </details>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ C
function oneRoofM3(r: CResult): number | null {
  const get = (id: string) => {
    const a = r.assumptions.find((x) => x.id === id);
    return a && typeof a.value === 'number' ? a.value : null;
  };
  const c = get('collection_coefficient');
  const e = get('injection_efficiency');
  if (c == null || e == null || !r.rain.annual_mm) return null;
  return (100 * r.rain.annual_mm) / 1000 * c * e;
}

function DiTab({ m, r, onAddSite }: { m: ModuleOutput<CResult>; r: CResult; onAddSite: () => void }) {
  const t = r.totals;
  const roof = oneRoofM3(r);
  if (r.sites.length === 0) {
    return (
      <>
        <div className="empty-di">
          <svg className="empty-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5C9 7 5.5 10.6 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10.6 15 7 12 2.5Z" fill="currentColor" /></svg>
          <h4>No DI sites yet</h4>
          <p>Add the defunct handpumps you plan to use on the map, then press <b>Assess this spring</b> again to see how much water they could add.</p>
          <button type="button" className="btn btn-primary" onClick={onAddSite}>+ Add DI site on the map</button>
        </div>
        {(roof != null || r.roofs_for_10pct != null) && (
          <section className="block">
            <h4>What one roof could do</h4>
            <ul className="bullets">
              {roof != null && <li>One 100 m² roof in {num(r.rain.annual_mm)} mm of rain could put about <b>{num(roof)} m³</b> ({litres(roof)}) a year into the ground.</li>}
              {r.roofs_for_10pct != null && <li>About <b>{num(r.roofs_for_10pct)}</b> roofs of 100 m² inside the likely springshed would add 10% to the dry-season flow.</li>}
            </ul>
          </section>
        )}
        <Bullets title="Notes" items={m.rationale} />
        <Warnings items={m.warnings} />
      </>
    );
  }
  const maxLean = Math.max(t.added_flow_lpm_lean.high, 0.01);
  return (
    <>
      <div className="stats">
        <Stat label="Water put into the ground" accent="var(--water)"
          value={<>{num(t.volume_m3_per_year)} <small>m³/year</small></>} sub={litres(t.volume_m3_per_year)} />
        <Stat label="Added dry-season flow" accent="var(--green)"
          value={<>{flow(t.added_flow_lpm_lean.mid)} <small>L/min</small></>}
          sub={<>Range {range(t.added_flow_lpm_lean)} L/min<RangeStrip {...t.added_flow_lpm_lean} max={maxLean * 1.1} /></>} />
        {t.pct_of_lean_flow && (
          <Stat label="Share of today's dry-season flow" accent="var(--green)"
            value={<>+{flow(t.pct_of_lean_flow.mid)}<small>%</small></>}
            sub={`${range(t.pct_of_lean_flow)}% of ${flow(t.lean_flow_lpm)} L/min`} />
        )}
        {r.roofs_for_10pct != null && (
          <Stat label="Roofs for +10% flow" accent="var(--earth)" value={num(r.roofs_for_10pct)} sub="100 m² roofs inside the likely springshed" />
        )}
      </div>
      {!t.pct_of_lean_flow && <p className="hint">Add the lean-season flow in step 2 to see this as a share of today's flow.</p>}

      <section className="block">
        <h4>Each DI site</h4>
        <ol className="site-cards">
          {r.sites.map((s, i) => {
            const lc = locationClass[s.location_class];
            return (
              <li key={s.id} className="site-card" style={{ borderLeftColor: lc.color }}>
                <div className="site-card-head">
                  <span className="site-num sm" style={{ background: lc.color }}>{i + 1}</span>
                  <b>{s.name}</b>
                  <span className="badge" style={{ background: lc.color }}>{lc.label}</span>
                </div>
                <p className="small site-note">{s.location_note}</p>
                <dl className="site-facts">
                  <div><dt>Water / year</dt><dd>{num(s.volume_m3_per_year)} m³</dd></div>
                  <div><dt>Reaches spring</dt><dd>{pct(s.share_reaching_spring.mid)} <span className="muted">({pct(s.share_reaching_spring.low)}–{pct(s.share_reaching_spring.high)})</span></dd></div>
                  <div><dt>Added dry flow</dt><dd>{flow(s.added_flow_lpm_lean.mid)} L/min <span className="muted">({range(s.added_flow_lpm_lean)})</span></dd></div>
                  <div><dt>Water level rise</dt><dd>{range(s.water_level_rise_m, (n) => n.toFixed(2))} m</dd></div>
                  <div><dt>Travel time</dt><dd>{s.travel_time_days ? `${num(s.travel_time_days.low)}–${num(s.travel_time_days.high)} days` : '–'}</dd></div>
                  <div><dt>Roof · distance</dt><dd>{num(s.roof_area_m2)} m² · {num(s.distance_to_spring_m)} m{s.height_above_spring_m != null ? `, ${s.height_above_spring_m >= 0 ? `${num(s.height_above_spring_m)} m above` : `${num(-s.height_above_spring_m)} m below`}` : ''}</dd></div>
                </dl>
                {s.flags.length > 0 && <ul className="flags">{s.flags.map((f, k) => <li key={k}>{f}</li>)}</ul>}
              </li>
            );
          })}
        </ol>
      </section>

      {(r.rain.monthly_mm || r.monthly_injection_m3) && (
        <section className="block">
          <h4>Through the year</h4>
          <p className="hint">Most water goes in during the monsoon (June–September). It comes out slowly over the following months.</p>
          <div className="monthly-pair">
            {r.rain.monthly_mm && <MonthlyBars title="Rain" unit="mm" values={r.rain.monthly_mm} color="#7fb3d8" />}
            {r.monthly_injection_m3 && <MonthlyBars title="Water put into the ground, all sites" unit="m³" values={r.monthly_injection_m3} color="#0b6e8a" />}
          </div>
          <p className="hint">Rain: {num(r.rain.annual_mm)} mm a year ({r.rain.source}).</p>
          <details className="table-view">
            <summary>Show as a table</summary>
            <div className="table-wrap">
              <table className="table compact">
                <thead><tr><th>Month</th>{MONTHS.map((mo) => <th key={mo} className="num">{mo}</th>)}</tr></thead>
                <tbody>
                  {r.rain.monthly_mm && <tr><td>Rain (mm)</td>{r.rain.monthly_mm.map((v, i) => <td key={i} className="num">{num(v)}</td>)}</tr>}
                  {r.monthly_injection_m3 && <tr><td>Into ground (m³)</td>{r.monthly_injection_m3.map((v, i) => <td key={i} className="num">{num(v, 1)}</td>)}</tr>}
                </tbody>
              </table>
            </div>
          </details>
        </section>
      )}

      <Bullets title="What this means" items={m.rationale} />
      <Bullets title="How to check if it works" items={r.monitoring_plan} />
      <Bullets title="For comparison" items={r.benchmarks} />
      {r.assumptions.length > 0 && (
        <section className="block">
          <h4>Assumptions used</h4>
          <div className="table-wrap">
            <table className="table compact">
              <tbody>
                {r.assumptions.map((a) => (
                  <tr key={a.id}>
                    <td>{a.label}<div className="hint">{a.note}</div></td>
                    <td className="num nowrap">{typeof a.value === 'number' ? num(a.value, 2) : a.value} {a.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <Warnings items={m.warnings} />
    </>
  );
}

// ------------------------------------------------------------------ before the first result
export function HowItWorks({ demo, onExample }: { demo: boolean; onExample: () => void }) {
  return (
    <div className="how">
      <h2>How it works</h2>
      <p>Tell the tool about one spring. In about half a minute you get three answers, drawn on the map.</p>
      <ol className="how-list">
        <li>
          <span className="how-icon how-a" aria-hidden="true">A</span>
          <div><b>Vulnerability</b><p>A score from 0 to 100: how much at risk the spring is, and why.</p></div>
        </li>
        <li>
          <span className="how-icon how-b" aria-hidden="true">B</span>
          <div><b>Springshed</b><p>Where the spring's water most likely soaks into the ground uphill, with good spots for recharge work.</p></div>
        </li>
        <li>
          <span className="how-icon how-c" aria-hidden="true">C</span>
          <div><b>DI impact</b><p>How much extra water rooftop rain put into defunct handpumps could give the spring in the dry months.</p></div>
        </li>
      </ol>
      <p className="hint">Start with step 1 on the left. Field answers and DI sites are optional but make the answer better.</p>
      <button type="button" className="btn" onClick={onExample}>{demo ? 'Fill in the example spring' : 'Try an example spring'}</button>
    </div>
  );
}
