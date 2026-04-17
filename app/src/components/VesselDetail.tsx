import type { VesselRow } from "../lib/duckdb";

interface Props {
  vessel: VesselRow;
  onClose: () => void;
}

const row = (label: string, value: string | number | null | undefined) => (
  <tr key={label}>
    <td
      style={{
        color: "#718096",
        paddingRight: "0.75rem",
        paddingBottom: "0.3rem",
        whiteSpace: "nowrap",
        fontSize: "0.72rem",
        verticalAlign: "top",
      }}
    >
      {label}
    </td>
    <td
      style={{
        color: "#e2e8f0",
        paddingBottom: "0.3rem",
        fontSize: "0.78rem",
        wordBreak: "break-all",
      }}
    >
      {value ?? "—"}
    </td>
  </tr>
);

function confidenceColor(c: number): string {
  if (c >= 0.75) return "#fc8181";
  if (c >= 0.5) return "#f6ad55";
  return "#68d391";
}

export default function VesselDetail({ vessel, onClose }: Props) {
  return (
    <div
      style={{
        borderTop: "1px solid #2d3748",
        background: "#0f1117",
        padding: "0.75rem 1rem",
        flexShrink: 0,
      }}
    >
      {/* Title row */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "0.6rem",
          gap: "0.5rem",
        }}
      >
        <div>
          <div
            style={{
              fontWeight: 600,
              fontSize: "0.85rem",
              color: "#93c5fd",
              lineHeight: 1.3,
            }}
          >
            {vessel.vessel_name || vessel.mmsi}
          </div>
          <div style={{ fontSize: "0.68rem", color: "#4a5568", marginTop: 2 }}>
            MMSI {vessel.mmsi}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            color: "#4a5568",
            cursor: "pointer",
            fontSize: "1rem",
            lineHeight: 1,
            padding: "0 0.2rem",
            flexShrink: 0,
          }}
          aria-label="Close detail panel"
        >
          ✕
        </button>
      </div>

      {/* Confidence badge */}
      <div style={{ marginBottom: "0.75rem" }}>
        <span
          style={{
            display: "inline-block",
            padding: "0.2rem 0.6rem",
            borderRadius: 4,
            background: "#1a1f2e",
            border: `1px solid ${confidenceColor(vessel.confidence)}`,
            color: confidenceColor(vessel.confidence),
            fontSize: "0.78rem",
            fontWeight: 600,
            fontFamily: "ui-monospace, monospace",
          }}
        >
          confidence {vessel.confidence.toFixed(3)}
        </span>
      </div>

      {/* Details table */}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {row("Flag", vessel.flag)}
          {row("Type", vessel.vessel_type)}
          {row("Region", vessel.region)}
          {row("Last seen", vessel.last_seen)}
          {vessel.last_lat != null &&
            vessel.last_lon != null &&
            row(
              "Position",
              `${vessel.last_lat.toFixed(4)}°, ${vessel.last_lon.toFixed(4)}°`
            )}
        </tbody>
      </table>
    </div>
  );
}
