import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { VesselRow } from "../lib/duckdb";

interface Props {
  vessels: VesselRow[];
  selectedMmsi: string | null;
  onSelect: (mmsi: string) => void;
}

const SOURCE_ID = "vessels";
const LAYER_CIRCLE = "vessels-circle";
const LAYER_SELECTED = "vessels-selected";

export default function VesselMap({ vessels, selectedMmsi, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<InstanceType<typeof maplibregl.Map> | null>(null);
  const popupRef = useRef<InstanceType<typeof maplibregl.Popup> | null>(null);

  // ── Initialise map once ──────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm-tiles", type: "raster", source: "osm" }],
        glyphs:
          "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      },
      center: [103.8, 1.3],
      zoom: 4,
    });

    map.on("load", () => {
      // GeoJSON source — updated on every data change
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      // Unselected vessels
      map.addLayer({
        id: LAYER_CIRCLE,
        type: "circle",
        source: SOURCE_ID,
        filter: ["!=", ["get", "mmsi"], ""],
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["get", "confidence"],
            0,
            4,
            1,
            9,
          ],
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "confidence"],
            0,
            "#68d391",
            0.5,
            "#f6ad55",
            0.75,
            "#fc8181",
            1,
            "#e53e3e",
          ],
          "circle-opacity": 0.85,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0f1117",
        },
      });

      // Selected vessel highlight ring
      map.addLayer({
        id: LAYER_SELECTED,
        type: "circle",
        source: SOURCE_ID,
        filter: ["==", ["get", "mmsi"], ""],
        paint: {
          "circle-radius": 14,
          "circle-color": "transparent",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#63b3ed",
        },
      });

      map.on("click", LAYER_CIRCLE, (e) => {
        if (!e.features?.length) return;
        const props = e.features[0].properties as VesselRow;
        onSelect(props.mmsi);
      });

      map.on("mouseenter", LAYER_CIRCLE, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", LAYER_CIRCLE, () => {
        map.getCanvas().style.cursor = "";
      });
    });

    mapRef.current = map;
    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      className: "vessel-popup",
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [onSelect]);

  // ── Update source when vessels change ────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;

    const source = map.getSource(SOURCE_ID) as
      | maplibregl.GeoJSONSource
      | undefined;
    if (!source) return;

    const features = vessels
      .filter((v) => v.last_lat != null && v.last_lon != null)
      .map((v) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [v.last_lon!, v.last_lat!],
        },
        properties: v,
      }));

    source.setData({ type: "FeatureCollection", features });
  }, [vessels]);

  // ── Highlight selected vessel ─────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;

    map.setFilter(LAYER_SELECTED, [
      "==",
      ["get", "mmsi"],
      selectedMmsi ?? "",
    ]);

    if (!selectedMmsi) {
      popupRef.current?.remove();
      return;
    }

    const vessel = vessels.find((v) => v.mmsi === selectedMmsi);
    if (!vessel || vessel.last_lat == null || vessel.last_lon == null) return;

    const html = `
      <div style="font-family:ui-monospace,monospace;font-size:0.78rem;color:#e2e8f0;padding:0.25rem 0;">
        <strong>${vessel.vessel_name || vessel.mmsi}</strong><br/>
        MMSI: ${vessel.mmsi}<br/>
        Flag: ${vessel.flag || "—"} &nbsp; Type: ${vessel.vessel_type || "—"}<br/>
        Confidence: <strong style="color:#fc8181">${vessel.confidence.toFixed(3)}</strong><br/>
        Region: ${vessel.region || "—"}
      </div>
    `;

    popupRef.current
      ?.setLngLat([vessel.last_lon, vessel.last_lat])
      .setHTML(html)
      .addTo(map);

    map.flyTo({
      center: [vessel.last_lon, vessel.last_lat],
      zoom: Math.max(map.getZoom(), 6),
      speed: 1.4,
    });
  }, [selectedMmsi, vessels]);

  return (
    <div
      ref={containerRef}
      style={{ flex: 1, minHeight: 0 }}
    />
  );
}
