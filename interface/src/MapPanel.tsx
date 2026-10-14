import { useEffect, useRef, useState } from 'preact/hooks';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Point } from './types';

type Props = {
  point: Point | null;
  onSelect: (point: Point) => void;
};

// The initial view frames the pilot region; it is not a spring location or analytical input.
const INITIAL_VIEW: L.LatLngExpression = [30.3, 78.4];

export default function MapPanel({ point, onSelect }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const onSelectRef = useRef(onSelect);
  const [tilesUnavailable, setTilesUnavailable] = useState(false);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!element.current || map.current) return;
    const instance = L.map(element.current, {
      zoomControl: false,
      scrollWheelZoom: false,
      preferCanvas: true,
    }).setView(INITIAL_VIEW, 9);
    map.current = instance;

    L.control.zoom({ position: 'topright' }).addTo(instance);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',
    })
      .on('tileerror', () => setTilesUnavailable(true))
      .addTo(instance);

    instance.on('click', (event: L.LeafletMouseEvent) => {
      onSelectRef.current({ latitude: event.latlng.lat, longitude: event.latlng.lng });
    });

    return () => {
      instance.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current) return;
    if (marker.current) {
      marker.current.remove();
      marker.current = null;
    }
    if (!point) return;
    const latLng: L.LatLngExpression = [point.latitude, point.longitude];
    marker.current = L.circleMarker(latLng, {
      radius: 10,
      color: '#ffffff',
      weight: 3,
      fillColor: '#116e67',
      fillOpacity: 1,
      className: 'spring-marker',
    }).addTo(map.current);
    map.current.setView(latLng, Math.max(map.current.getZoom(), 12), { animate: true });
  }, [point?.latitude, point?.longitude]);

  return (
    <div className="map-wrap">
      <div ref={element} className="map-canvas" role="region" aria-label="Map for choosing a spring location" />
      <div className="map-top-note">
        <span className="map-top-dot" />
        {point ? 'Spring point selected' : 'Tap the map to place a spring point'}
      </div>
      <div className="map-legend" aria-label="Map legend">
        <div><span className="legend-spring" /> Spring point</div>
        <div><span className="legend-boundary" /> Candidate boundary <small>not available</small></div>
      </div>
      {tilesUnavailable && (
        <div className="map-offline" role="status">Map background needs a connection. Coordinate entry still works.</div>
      )}
    </div>
  );
}
