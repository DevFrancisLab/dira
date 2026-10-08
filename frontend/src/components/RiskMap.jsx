import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { BuildingRiskCard } from "./BuildingRiskCard";
import { EventSelector } from "./EventSelector";
import { metricOf } from "../format";
import { mapController } from "../map/controller";

const COLORS = { none: "#94A3B8", low: "#0F766E", mid: "#D97706", high: "#EA580C", severe: "#C8102E" };

function displayCuts(losses) {
  const positive = losses.filter((value) => value > 0).sort((a, b) => a - b);
  if (!positive.length) return [Infinity, Infinity, Infinity];
  const at = (share) => positive[Math.min(positive.length - 1, Math.floor(share * positive.length))];
  return [at(0.25), at(0.5), at(0.75)];
}

function colorFor(loss, cuts) {
  if (!(loss > 0)) return COLORS.none;
  if (loss <= cuts[0]) return COLORS.low;
  if (loss <= cuts[1]) return COLORS.mid;
  if (loss <= cuts[2]) return COLORS.high;
  return COLORS.severe;
}

export function RiskMap({ data, tier, assumption, selectedId, highlighted, visible }) {
  const mapNode = useRef(null);
  const mapRef = useRef(null);
  const markers = useRef(new Map());
  const [query, setQuery] = useState("");
  const [openSearch, setOpenSearch] = useState(false);
  const byId = useMemo(() => new Map(data.buildings.map((building) => [building.loc_id, building])), [data]);
  const tierMeta = data.tiers.find((item) => item.id === tier);
  const selected = selectedId ? byId.get(selectedId) : null;

  useEffect(() => {
    if (!mapNode.current || mapRef.current) return undefined;
    const map = L.map(mapNode.current, { zoomControl: false, minZoom: 10, maxZoom: 18 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    for (const building of data.buildings) {
      const marker = L.circleMarker([building.lat, building.lon], {
        radius: 5,
        weight: 1,
        color: COLORS.none,
        fillColor: COLORS.none,
        fillOpacity: 0.9,
      });
      marker.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        mapController.selectBuilding(building.loc_id);
      });
      marker.addTo(map);
      markers.current.set(building.loc_id, marker);
    }
    map.fitBounds(data.buildings.map((building) => [building.lat, building.lon]), { padding: [28, 28] });
    mapRef.current = map;
    mapController.bindMap(map);
    return () => {
      mapController.unbindMap(map);
      map.remove();
      mapRef.current = null;
      markers.current.clear();
    };
  }, [data]);

  useEffect(() => {
    if (!visible || !mapRef.current) return;
    mapRef.current.invalidateSize();
  }, [visible]);

  useEffect(() => {
    if (!mapRef.current || !selectedId) return;
    const building = byId.get(selectedId);
    if (!building) return;
    const zoom = mapRef.current.getZoom() < 13 ? 14 : mapRef.current.getZoom();
    mapController.flyTo(building.lat, building.lon, zoom);
  }, [selectedId, byId]);

  useEffect(() => {
    if (!mapRef.current || !highlighted.length) return;
    const points = highlighted.map((id) => byId.get(id)).filter(Boolean);
    if (points.length === 1) mapController.flyTo(points[0].lat, points[0].lon, 15);
    else mapRef.current.fitBounds(points.map((building) => [building.lat, building.lon]), { padding: [48, 48] });
  }, [highlighted, byId]);

  useEffect(() => {
    const losses = data.buildings.map((building) => metricOf(building, assumption, tier).loss_kes);
    const cuts = displayCuts(losses);
    const highlightSet = new Set(highlighted);
    for (const building of data.buildings) {
      const loss = metricOf(building, assumption, tier).loss_kes;
      const active = building.loc_id === selectedId || highlightSet.has(building.loc_id);
      const fill = colorFor(loss, cuts);
      const marker = markers.current.get(building.loc_id);
      if (!marker) continue;
      marker.setStyle({
        radius: active ? 8 : loss > 0 ? 5.5 : 4,
        color: active ? "#003B70" : fill,
        weight: active ? 2 : 1,
        fillColor: fill,
        fillOpacity: loss > 0 ? 0.92 : 0.55,
      });
      if (loss > 0 || active) marker.bringToFront();
    }
  }, [data, tier, assumption, selectedId, highlighted]);

  const results = searchItems(data, query);

  return (
    <section className="map-page">
      <div className="map-toolbar">
        <EventSelector data={data} tier={tier} assumption={assumption} />
        <form
          className="search"
          onSubmit={(event) => {
            event.preventDefault();
            if (results[0]) choose(results[0]);
          }}
        >
          <input
            value={query}
            placeholder="Search hotspot or building ID"
            aria-label="Search hotspot or building ID"
            onChange={(event) => {
              setQuery(event.target.value);
              setOpenSearch(true);
            }}
            onFocus={() => setOpenSearch(true)}
          />
          {openSearch && results.length > 0 ? (
            <div className="search-results">
              {results.map((item) => (
                <button key={item.key} type="button" onClick={() => choose(item)}>
                  <span>{item.label}</span>
                  <small>{item.detail}</small>
                </button>
              ))}
            </div>
          ) : null}
        </form>
        <div className="zoom">
          <button type="button" aria-label="Zoom in" onClick={() => mapController.zoomIn()}>+</button>
          <button type="button" aria-label="Zoom out" onClick={() => mapController.zoomOut()}>−</button>
        </div>
      </div>
      <div className="map-stage">
        <div ref={mapNode} className="map-canvas" />
        <div className="legend">
          <span><i style={{ background: COLORS.none }} /> Not flagged</span>
          <span><i style={{ background: COLORS.low }} /> Low</span>
          <span><i style={{ background: COLORS.mid }} /> Moderate</span>
          <span><i style={{ background: COLORS.high }} /> High</span>
          <span><i style={{ background: COLORS.severe }} /> Severe</span>
        </div>
        {selected ? (
          <BuildingRiskCard
            building={selected}
            tier={tierMeta}
            assumption={assumption}
            onClose={() => mapController.selectBuilding("")}
          />
        ) : null}
      </div>
    </section>
  );

  function choose(item) {
    setOpenSearch(false);
    setQuery(item.label);
    if (item.hotspot) mapController.flyTo(item.hotspot.lat, item.hotspot.lon, 14);
    else mapController.selectBuilding(item.building.loc_id);
  }
}

function searchItems(data, query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const rank = (value) => {
    const text = value.toLowerCase();
    if (text === q) return 0;
    if (text.startsWith(q)) return 1;
    return 2;
  };
  const hotspots = data.hotspots
    .filter((hotspot) => hotspot.name.toLowerCase().includes(q))
    .sort((a, b) => rank(a.name) - rank(b.name))
    .map((hotspot) => ({
      key: `h-${hotspot.name}`,
      label: hotspot.name,
      detail: "Named area",
      hotspot,
    }));
  const buildings = data.buildings
    .filter((building) => building.loc_id.toLowerCase().includes(q))
    .sort((a, b) => rank(a.loc_id) - rank(b.loc_id))
    .slice(0, 6)
    .map((building) => ({
      key: building.loc_id,
      label: building.loc_id,
      detail: "Building",
      building,
    }));
  return [...hotspots, ...buildings].slice(0, 8);
}
