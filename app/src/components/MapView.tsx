import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Circle, CircleMarker, GeoJSON, ImageOverlay, LayerGroup, LayersControl, MapContainer, Marker, Popup, TileLayer, Tooltip,
  useMap, useMapEvents,
} from 'react-leaflet';
import type { AssessResponse, DatasetSpring, DiSite, DiSiteResult, Feature } from '../api';
import { locationClass, num } from '../format';

export type Tab = 'A' | 'B' | 'C';
export type Placing = 'none' | 'spring' | 'site';
export type Focus = { lat: number; lon: number; zoom: number; n: number };

type Props = {
  springs: DatasetSpring[];
  point: { lat: number; lon: number } | null;
  springName: string;
  result: AssessResponse | null;
  tab: Tab;
  sites: DiSite[];
  placing: Placing;
  canCancel: boolean;
  focus: Focus | null;
  onPlace: (lat: number, lon: number) => void;
  onCancelPlacing: () => void;
  onSpringDrag: (lat: number, lon: number) => void;
  onSiteMove: (id: string, lat: number, lon: number) => void;
  onUseSpring: (s: DatasetSpring) => void;
};

const UTTARAKHAND: L.LatLngBoundsExpression = [[28.7, 77.6], [31.4, 81.1]];

const springIcon = L.divIcon({
  className: 'pin-wrap',
  html: '<div class="pin pin-spring"><span></span></div>',
  iconSize: [30, 40],
  iconAnchor: [15, 38],
  popupAnchor: [0, -34],
  tooltipAnchor: [12, -24],
});

const spotIcon = L.divIcon({
  className: 'pin-wrap',
  html: '<div class="spot-icon" aria-hidden="true">★</div>',
  iconSize: [26, 26],
  iconAnchor: [13, 13],
  popupAnchor: [0, -12],
});

function siteIcon(index: number, cls: DiSiteResult['location_class'] | null, big: boolean) {
  const color = cls ? locationClass[cls].color : '#ffffff';
  const size = big ? 30 : 24;
  return L.divIcon({
    className: 'pin-wrap',
    html: `<div class="site-icon${cls ? '' : ' site-new'}" style="background:${color};width:${size}px;height:${size}px">${index + 1}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

const ZONE_STYLE: Record<'small' | 'likely' | 'large', { color: string; fill: string }> = {
  small: { color: '#14532d', fill: '#1f7a45' },
  likely: { color: '#1f7a45', fill: '#3f9d55' },
  large: { color: '#5d9c4c', fill: '#a7d58f' },
};

function zoneStyle(scenario: 'small' | 'likely' | 'large', tab: Tab): L.PathOptions {
  const s = ZONE_STYLE[scenario];
  const fillBase = scenario === 'large' ? 0.28 : scenario === 'likely' ? 0.32 : 0.4;
  const k = tab === 'B' ? 1 : tab === 'C' ? 0.7 : 0.25;
  return {
    color: s.color,
    weight: tab === 'A' ? 1 : scenario === 'likely' ? 2.5 : 1.5,
    opacity: tab === 'A' ? 0.5 : 0.9,
    fillColor: s.fill,
    fillOpacity: fillBase * k,
  };
}

function boundsOf(features: (Feature | null | undefined)[]): L.LatLngBounds | null {
  let b: L.LatLngBounds | null = null;
  for (const f of features) {
    if (!f) continue;
    try {
      const fb = L.geoJSON(f as any).getBounds();
      if (fb.isValid()) b = b ? b.extend(fb) : fb;
    } catch {
      /* ignore bad geometry */
    }
  }
  return b;
}

/** Moves the view when the user picks a spring, gets a result or switches tab. */
function ViewController({ result, tab, point, sites, focus }: Pick<Props, 'result' | 'tab' | 'point' | 'sites' | 'focus'>) {
  const map = useMap();
  const lastFocus = useRef(0);
  useEffect(() => {
    if (focus && focus.n !== lastFocus.current) {
      lastFocus.current = focus.n;
      map.flyTo([focus.lat, focus.lon], focus.zoom, { duration: 0.8 });
    }
  }, [focus, map]);
  useEffect(() => {
    if (!result) return;
    const s = result.spring;
    const springBounds = L.latLng(s.latitude, s.longitude).toBounds(1300);
    let b: L.LatLngBounds = springBounds;
    const B = result.B.result;
    if (tab !== 'A' && B) {
      const zb = boundsOf([B.surface_catchment.geojson, ...B.zones.map((z) => z.geojson)]);
      if (zb) b = zb.extend(L.latLng(s.latitude, s.longitude));
    }
    if (tab === 'C') for (const site of sites) b = b.extend(L.latLng(site.latitude, site.longitude));
    map.flyToBounds(b.pad(0.15), { duration: 0.7, maxZoom: 17 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result?.run_id, tab, map]);
  useEffect(() => {
    if (!result && point && !focus) map.setView([point.lat, point.lon], 14);
    // only on first mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

/** Keeps Leaflet's size right when the page layout changes. */
function SizeWatcher() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const ro = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

function ClickHandler({ placing, onPlace }: { placing: Placing; onPlace: Props['onPlace'] }) {
  useMapEvents({
    click(e) {
      if (placing !== 'none') onPlace(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** Creates the map panes once, before any layer that uses them is added. */
const PANES: [string, number][] = [['heat', 380], ['zones', 400], ['lines', 420], ['dataset', 450]];
function CreatePanes() {
  const map = useMap();
  for (const [name, z] of PANES) {
    if (!map.getPane(name)) map.createPane(name).style.zIndex = String(z);
  }
  return null;
}

export default function MapView(props: Props) {
  const { springs, point, result, tab, sites, placing } = props;
  const [tilesFailed, setTilesFailed] = useState(false);
  const [heatOn, setHeatOn] = useState(false);
  const [heatOpacity, setHeatOpacity] = useState(0.6);
  const [legendOpen, setLegendOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 900);
  const counts = useRef({ loaded: 0, failed: 0 });
  const tileHandlers = useMemo(() => ({
    tileload: () => { counts.current.loaded += 1; setTilesFailed(false); },
    tileerror: () => {
      counts.current.failed += 1;
      if (counts.current.failed >= 4 && counts.current.loaded === 0) setTilesFailed(true);
    },
  }), []);

  const B = result?.B.result ?? null;
  const C = result?.C.result ?? null;
  const siteClass = useMemo(() => {
    const m = new Map<string, DiSiteResult>();
    for (const s of C?.sites ?? []) m.set(s.id, s);
    return m;
  }, [C]);
  const runKey = result?.run_id ?? 'none';
  const resultSpring = result ? L.latLng(result.spring.latitude, result.spring.longitude) : null;
  const overlay = B?.potential_overlay ?? null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') props.onCancelPlacing(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [props]);

  // DI sites belong to the DI impact tab; before any result, or while placing one, they show everywhere.
  const showSites = !result || tab === 'C' || placing === 'site';
  const legend: { key: string; label: string; swatch: JSX.Element }[] = [];
  const zonesSwatch = (
    <span className="lg-zones">
      {(['small', 'likely', 'large'] as const).map((z) => <i key={z} className="lg-fill" style={{ background: ZONE_STYLE[z].fill }} />)}
    </span>
  );
  legend.push({ key: 'spring', label: 'Your spring', swatch: <i className="lg-pin" /> });
  if (springs.length && (!B || tab === 'A')) legend.push({ key: 'ds', label: 'Springs in the dataset', swatch: <i className="lg-dot" /> });
  if (B) {
    if (tab === 'A') legend.push({ key: 'r', label: '500 m around the spring', swatch: <i className="lg-ring" /> });
    if (B.surface_catchment.geojson && tab !== 'A') legend.push({ key: 'c', label: 'Surface catchment', swatch: <i className="lg-dash" /> });
    legend.push({ key: 'z', label: 'Springshed (recharge area): small, likely, large', swatch: zonesSwatch });
    if (tab === 'B') {
      if (B.faults.features.length) legend.push({ key: 'f', label: 'Fault or thrust', swatch: <i className="lg-line" style={{ background: '#d1352b' }} /> });
      if (B.lineaments.features.length) legend.push({ key: 'l', label: 'Lineament (possible crack line)', swatch: <i className="lg-line lg-dashed" /> });
      if (B.streams.features.length) legend.push({ key: 's', label: 'Stream', swatch: <i className="lg-line" style={{ background: '#2b7bbd' }} /> });
    }
    if (tab !== 'A' && B.recharge_spots.length) legend.push({ key: 'rs', label: 'Suggested recharge spot', swatch: <i className="lg-star">★</i> });
  }
  if (showSites && sites.length) {
    const classes = new Set<DiSiteResult['location_class'] | null>();
    for (const s of sites) {
      const r = siteClass.get(s.id);
      classes.add(r && r.latitude === s.latitude && r.longitude === s.longitude ? r.location_class : null);
    }
    for (const c of Object.keys(locationClass) as DiSiteResult['location_class'][]) {
      if (classes.has(c)) legend.push({ key: `di-${c}`, label: `DI site: ${locationClass[c].label.toLowerCase()}`, swatch: <i className="lg-site" style={{ background: locationClass[c].color }} /> });
    }
    if (classes.has(null)) legend.push({ key: 'di-new', label: 'DI site (not assessed yet)', swatch: <i className="lg-site lg-site-new" /> });
  }

  return (
    <div className={`map-wrap${placing !== 'none' ? ' placing' : ''}`}>
      <MapContainer bounds={UTTARAKHAND} className="map" preferCanvas zoomControl scrollWheelZoom worldCopyJump={false}>
        <CreatePanes />
        <SizeWatcher />
        <ClickHandler placing={placing} onPlace={props.onPlace} />
        <ViewController result={result} tab={tab} point={point} sites={sites} focus={props.focus} />
        <TileWatchReset onReset={() => { counts.current = { loaded: 0, failed: 0 }; setTilesFailed(false); }} />
        <LayersControl position="topright">
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics"
              maxZoom={19}
              eventHandlers={tileHandlers}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer checked name="Terrain">
            <TileLayer
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
              attribution='Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Style &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'
              maxZoom={17}
              maxNativeZoom={17}
              eventHandlers={tileHandlers}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Streets">
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              maxZoom={19}
              eventHandlers={tileHandlers}
            />
          </LayersControl.BaseLayer>

          {springs.length > 0 && (
            <LayersControl.Overlay checked name="Springs in the dataset">
              <LayerGroup>
                {springs.map((s) => (
                  <CircleMarker key={s.id} center={[s.latitude, s.longitude]} radius={4.5} pane="dataset" bubblingMouseEvents={false}
                    pathOptions={{ color: '#ffffff', weight: 1.2, fillColor: '#0b6e8a', fillOpacity: 0.9 }}>
                    <Popup>
                      <div className="pop">
                        <strong>{s.name}</strong>
                        <div>{[s.village, s.district].filter(Boolean).join(', ')}</div>
                        <div className="muted">{s.elevation_m != null ? `${num(s.elevation_m)} m · ` : ''}{s.source}</div>
                        <button type="button" className="btn btn-small btn-primary" onClick={() => props.onUseSpring(s)}>Use this spring</button>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>
          )}

          {B && B.faults.features.length > 0 && (
            <LayersControl.Overlay checked name="Faults">
              <GeoJSON key={`f-${runKey}`} data={B.faults as any} pane="lines"
                style={() => ({ color: '#d1352b', weight: 2.5, opacity: 0.9 })}
                onEachFeature={(f, layer) => layer.bindTooltip(`${f.properties?.name || 'Fault'}${f.properties?.type ? ` (${f.properties.type})` : ''}`, { sticky: true })} />
            </LayersControl.Overlay>
          )}
          {B && B.lineaments.features.length > 0 && (
            <LayersControl.Overlay checked name="Lineaments">
              <GeoJSON key={`l-${runKey}`} data={B.lineaments as any} pane="lines"
                style={() => ({ color: '#e08a1e', weight: 1.5, opacity: 0.95, dashArray: '5 5' })}
                onEachFeature={(_f, layer) => layer.bindTooltip('Lineament: a straight line on the elevation map that may follow a crack in the rock', { sticky: true })} />
            </LayersControl.Overlay>
          )}
          {B && B.streams.features.length > 0 && (
            <LayersControl.Overlay checked name="Streams">
              <GeoJSON key={`s-${runKey}`} data={B.streams as any} pane="lines"
                style={(f) => ({ color: '#2b7bbd', weight: 0.8 + 0.9 * Number(f?.properties?.order ?? 1), opacity: 0.85 })} />
            </LayersControl.Overlay>
          )}
        </LayersControl>

        {overlay && heatOn && (
          <ImageOverlay key={`h-${runKey}`} url={overlay.image} bounds={overlay.bounds} opacity={heatOpacity} pane="heat" />
        )}

        {B && (['large', 'likely', 'small'] as const).map((sc) => {
          const z = B.zones.find((x) => x.scenario === sc);
          return z ? (
            <GeoJSON key={`z-${sc}-${runKey}-${tab}`} data={z.geojson as any} pane="zones" style={() => zoneStyle(sc, tab)}
              onEachFeature={(_f, layer) => layer.bindTooltip(`Springshed, ${sc}: ${num(z.area_ha, 1)} ha`, { sticky: true })} />
          ) : null;
        })}
        {B?.surface_catchment.geojson && (
          <GeoJSON key={`c-${runKey}-${tab}`} data={B.surface_catchment.geojson as any} pane="zones"
            style={() => ({ color: '#1d5f99', weight: tab === 'B' ? 2.5 : 1.8, dashArray: '7 6', fill: false, opacity: tab === 'A' ? 0.5 : 0.95 })}
            onEachFeature={(_f, layer) => layer.bindTooltip(`Surface catchment: ${num(B.surface_catchment.area_ha, 1)} ha (where rain runs off towards the spring)`, { sticky: true })} />
        )}

        {resultSpring && tab === 'A' && (
          <Circle center={resultSpring} radius={500} pathOptions={{ color: '#0b6e8a', weight: 2, dashArray: '2 6', fillColor: '#0b6e8a', fillOpacity: 0.06 }} />
        )}

        {B && tab !== 'A' && B.recharge_spots.map((s, i) => (
          <Marker key={`rs-${runKey}-${i}`} position={[s.latitude, s.longitude]} icon={spotIcon}>
            <Popup>
              <div className="pop">
                <strong>Suggested recharge spot {i + 1}</strong>
                <div>{s.reason}</div>
                <div className="muted">{num(s.elevation_m)} m · recharge potential {Math.round(s.potential * 100)}%</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {showSites && sites.map((s, i) => {
          const r = siteClass.get(s.id);
          const moved = r && (Math.abs(r.latitude - s.latitude) > 1e-6 || Math.abs(r.longitude - s.longitude) > 1e-6);
          const cls = r && !moved ? r.location_class : null;
          return (
            <Marker key={s.id} position={[s.latitude, s.longitude]} icon={siteIcon(i, cls, tab === 'C')} draggable
              eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); props.onSiteMove(s.id, ll.lat, ll.lng); } }}>
              <Tooltip direction="top" offset={[0, -12]}>{s.name || `DI site ${i + 1}`}</Tooltip>
              <Popup>
                <div className="pop">
                  <strong>{s.name || `DI site ${i + 1}`}</strong>
                  <div>Roof {num(s.roof_area_m2)} m²</div>
                  {cls && r ? <div><span className="badge" style={{ background: locationClass[cls].color }}>{locationClass[cls].label}</span><div>{r.location_note}</div></div>
                    : <div className="muted">Not assessed yet. Run the assessment again to see its effect.</div>}
                  <div className="muted">Drag the marker to move it.</div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {point && (
          <Marker position={[point.lat, point.lon]} icon={springIcon} draggable zIndexOffset={1000}
            eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); props.onSpringDrag(ll.lat, ll.lng); } }}>
            <Tooltip direction="top">{props.springName || 'Your spring'}</Tooltip>
          </Marker>
        )}
      </MapContainer>

      {placing !== 'none' && (
        <div className={`map-hint${props.canCancel ? '' : ' map-hint-soft'}`} role="status">
          <span>
            {placing === 'site' ? 'Click on the map where the defunct handpump is.'
              : props.canCancel ? 'Click on the map where the spring comes out.'
              : 'Click the map where the spring comes out, click a teal dot, or search on the left.'}
          </span>
          {props.canCancel && <button type="button" className="btn btn-small" onClick={props.onCancelPlacing}>Cancel</button>}
        </div>
      )}
      {tilesFailed && (
        <div className="map-note" role="status">The map background could not load (no internet?). Your spring and the results still show on a blank map.</div>
      )}

      <div className="map-legend" aria-label="Map legend">
        <details open={legendOpen} onToggle={(e) => setLegendOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Legend</summary>
          <ul>
            {legend.map((l) => <li key={l.key}>{l.swatch}<span>{l.label}</span></li>)}
          </ul>
          {overlay && (
            <div className="heat-ctl">
              <label className="check">
                <input type="checkbox" checked={heatOn} onChange={(e) => setHeatOn(e.target.checked)} />
                Recharge potential heat map
              </label>
              {heatOn && (
                <>
                  <label className="slider-row">
                    <span>See-through</span>
                    <input type="range" min={0.1} max={1} step={0.05} value={heatOpacity} onChange={(e) => setHeatOpacity(Number(e.target.value))} aria-label="Heat map opacity" />
                  </label>
                  <div className="heat-legend">
                    {overlay.legend.map((l) => <span key={l.label}><i style={{ background: l.color }} />{l.label}</span>)}
                  </div>
                </>
              )}
            </div>
          )}
        </details>
      </div>
    </div>
  );
}

/** Resets the tile failure counter when the user switches base layer. */
function TileWatchReset({ onReset }: { onReset: () => void }) {
  useMapEvents({ baselayerchange: onReset });
  return null;
}

