import { useState } from "react";
import type { VesselRow } from "../lib/duckdb";

interface Props {
  vessels: VesselRow[];
  selectedMmsi: string | null;
  onSelect: (mmsi: string) => void;
}

function confidenceColor(c: number): string {
  if (c >= 0.75) return "#fc8181";
  if (c >= 0.5) return "#f6ad55";
  return "#68d391";
}

export default function WatchlistTable({
  vessels,
  selectedMmsi,
  onSelect,
}: Props) {
  const [search, setSearch] = useState("");

  const filtered = search
    ? vessels.filter(
        (v) =>
          v.vessel_name?.toLowerCase().includes(search.toLowerCase()) ||
          v.mmsi?.includes(search) ||
          v.flag?.toLowerCase().includes(search.toLowerCase())
      )
    : vessels;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Search */}
      <div style={{ padding: "0.5rem 0.75rem", borderBottom: "1px solid #2d3748" }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search vessel / MMSI / flag…"
          style={{
            width: "100%",
            background: "#0f1117",
            border: "1px solid #2d3748",
            borderRadius: 4,
            color: "#e2e8f0",
            padding: "0.3rem 0.5rem",
            fontSize: "0.75rem",
            outline: "none",
          }}
        />
      </div>

      {/* Table */}
      <div style={{ overflowY: "auto", flex: 1 }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "0.72rem",
          }}
        >
          <thead>
            <tr
              style={{
                background: "#1a1f2e",
                position: "sticky",
                top: 0,
                zIndex: 1,
              }}
            >
              {["Vessel", "Flag", "Type", "Conf", "Region"].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "0.4rem 0.5rem",
                    textAlign: "left",
                    color: "#718096",
                    fontWeight: 600,
                    fontSize: "0.65rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    borderBottom: "1px solid #2d3748",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((v) => (
              <tr
                key={v.mmsi}
                onClick={() => onSelect(v.mmsi)}
                style={{
                  cursor: "pointer",
                  background:
                    selectedMmsi === v.mmsi ? "#1e3a5a" : "transparent",
                  borderBottom: "1px solid #1a1f2e",
                }}
                onMouseEnter={(e) => {
                  if (selectedMmsi !== v.mmsi)
                    (e.currentTarget as HTMLElement).style.background =
                      "#1e2a3a";
                }}
                onMouseLeave={(e) => {
                  if (selectedMmsi !== v.mmsi)
                    (e.currentTarget as HTMLElement).style.background =
                      "transparent";
                }}
              >
                <td
                  style={{
                    padding: "0.35rem 0.5rem",
                    maxWidth: 140,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={v.vessel_name}
                >
                  {v.vessel_name || v.mmsi}
                </td>
                <td style={{ padding: "0.35rem 0.5rem", color: "#a0aec0" }}>
                  {v.flag || "—"}
                </td>
                <td
                  style={{
                    padding: "0.35rem 0.5rem",
                    color: "#a0aec0",
                    maxWidth: 80,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={v.vessel_type}
                >
                  {v.vessel_type || "—"}
                </td>
                <td
                  style={{
                    padding: "0.35rem 0.5rem",
                    fontWeight: 700,
                    color: confidenceColor(v.confidence),
                  }}
                >
                  {v.confidence.toFixed(3)}
                </td>
                <td style={{ padding: "0.35rem 0.5rem", color: "#718096" }}>
                  {v.region || "—"}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    padding: "2rem",
                    textAlign: "center",
                    color: "#4a5568",
                  }}
                >
                  {vessels.length === 0 ? "No data — sync from R2 first." : "No results."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div
        style={{
          padding: "0.35rem 0.75rem",
          fontSize: "0.65rem",
          color: "#4a5568",
          borderTop: "1px solid #2d3748",
          flexShrink: 0,
        }}
      >
        {filtered.length} / {vessels.length} vessels
      </div>
    </div>
  );
}
