// Small hand-drawn SVG/HTML charts (no chart library).
import { MONTHS, classColor, num } from '../format';

export function Gauge({ score, label }: { score: number; label: string }) {
  const cx = 110, cy = 112, r = 88;
  const t = Math.max(0, Math.min(100, score)) / 100;
  const at = (v: number) => {
    const a = Math.PI * (1 - v);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  };
  const [x0, y0] = at(0);
  const [x1, y1] = at(1);
  const [xs, ys] = at(t);
  const color = classColor(label);
  const tick = (v: number) => {
    const a = Math.PI * (1 - v);
    return { x1: cx + (r - 14) * Math.cos(a), y1: cy - (r - 14) * Math.sin(a), x2: cx + (r + 14) * Math.cos(a), y2: cy - (r + 14) * Math.sin(a) };
  };
  return (
    <svg className="gauge" viewBox="0 0 220 128" role="img" aria-label={`Score ${score} of 100, ${label}`}>
      <defs>
        <linearGradient id="gauge-track" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="var(--risk-low)" />
          <stop offset="0.5" stopColor="var(--risk-med)" />
          <stop offset="1" stopColor="var(--risk-high)" />
        </linearGradient>
      </defs>
      <path d={`M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`} fill="none" stroke="url(#gauge-track)" strokeOpacity="0.22" strokeWidth="18" strokeLinecap="round" />
      {t > 0 && <path d={`M ${x0} ${y0} A ${r} ${r} 0 0 1 ${xs} ${ys}`} fill="none" stroke={color} strokeWidth="18" strokeLinecap="round" />}
      <line {...tick(t)} stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
      <text x={cx} y={cy - 22} textAnchor="middle" className="gauge-score" fill="var(--ink)">{Math.round(score)}</text>
      <text x={cx} y={cy - 2} textAnchor="middle" className="gauge-sub" fill="var(--ink-3)">of 100</text>
      <text x={x0} y={cy + 15} textAnchor="middle" className="gauge-end" fill="var(--ink-3)">0</text>
      <text x={x1} y={cy + 15} textAnchor="middle" className="gauge-end" fill="var(--ink-3)">100</text>
    </svg>
  );
}

const COVER_COLORS: Record<string, string> = {
  'tree cover': '#2d6a4f', forest: '#2d6a4f', cropland: '#d4a72c', grassland: '#9cc97e', shrubland: '#6f9a55',
  'built-up': '#b5524a', 'bare ground': '#a8a092', bare: '#a8a092', water: '#3a86c8', snow: '#c9d6df',
};
const FALLBACK = ['#5b7f95', '#8d6e97', '#c27c4e', '#7c8d4c', '#9aa1a9'];

export function StackedBar({ shares }: { shares: Record<string, number> }) {
  const entries = Object.entries(shares).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  const color = (k: string, i: number) => COVER_COLORS[k.toLowerCase()] ?? FALLBACK[i % FALLBACK.length];
  return (
    <div className="stacked">
      <div className="stacked-bar" role="img" aria-label={entries.map(([k, v]) => `${k} ${Math.round(v)}%`).join(', ')}>
        {entries.map(([k, v], i) => (
          <span key={k} style={{ flexGrow: v / total, background: color(k, i) }} title={`${k}: ${Math.round(v)}%`} />
        ))}
      </div>
      <ul className="stacked-legend">
        {entries.map(([k, v], i) => (
          <li key={k}><i style={{ background: color(k, i) }} />{k} <b>{Math.round(v)}%</b></li>
        ))}
      </ul>
    </div>
  );
}

/** One series of 12 monthly bars. Two of these stacked share the month axis (no dual axis). */
export function MonthlyBars({ values, unit, color, title }: { values: number[]; unit: string; color: string; title: string }) {
  const W = 360, H = 112, left = 34, bottom = 18, top = 10;
  const max = Math.max(...values, 1);
  const nice = niceMax(max);
  const bw = (W - left - 4) / 12;
  const y = (v: number) => top + (H - top - bottom) * (1 - v / nice);
  const peak = values.indexOf(Math.max(...values));
  return (
    <figure className="monthly">
      <figcaption>{title} <span className="muted">({unit})</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${values.map((v, i) => `${MONTHS[i]} ${num(v)}`).join(', ')}`}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={left} x2={W} y1={y(nice * f)} y2={y(nice * f)} stroke="var(--line)" strokeWidth="1" />
            <text x={left - 5} y={y(nice * f) + 3.5} textAnchor="end" className="axis">{num(nice * f)}</text>
          </g>
        ))}
        {values.map((v, i) => {
          const x = left + 2 + i * bw;
          const h = Math.max(0, y(0) - y(v));
          return (
            <g key={i} className="bar">
              <rect x={x} y={top} width={bw} height={H - top - bottom} fill="transparent">
                <title>{`${MONTHS[i]}: ${num(v, 1)} ${unit}`}</title>
              </rect>
              <path d={roundedTop(x + bw * 0.18, y(0), bw * 0.64, h, 3)} fill={color} pointerEvents="none" />
              {i === peak && v > 0 && <text x={x + bw / 2} y={y(v) - 3} textAnchor="middle" className="axis strong">{num(v)}</text>}
              <text x={x + bw / 2} y={H - 5} textAnchor="middle" className="axis">{MONTHS[i][0]}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

function roundedTop(x: number, base: number, w: number, h: number, r: number) {
  if (h <= 0) return '';
  const rr = Math.min(r, h, w / 2);
  return `M ${x} ${base} V ${base - h + rr} Q ${x} ${base - h} ${x + rr} ${base - h} H ${x + w - rr} Q ${x + w} ${base - h} ${x + w} ${base - h + rr} V ${base} Z`;
}

function niceMax(v: number) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

/** Low–mid–high range on a 0..max scale. */
export function RangeStrip({ low, mid, high, max }: { low: number; mid: number; high: number; max: number }) {
  const s = (v: number) => `${Math.max(0, Math.min(100, (v / (max || 1)) * 100))}%`;
  return (
    <div className="range-strip" aria-hidden="true">
      <span className="range-band" style={{ left: s(low), width: `calc(${s(high)} - ${s(low)})` }} />
      <span className="range-mid" style={{ left: s(mid) }} />
    </div>
  );
}
