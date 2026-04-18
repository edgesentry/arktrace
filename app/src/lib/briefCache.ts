/**
 * Analyst brief cache — persisted in DuckDB (OPFS-backed).
 *
 * Table: analyst_briefs(mmsi, brief, generated_at)
 * One row per vessel; loaded on vessel select so the LLM is only called
 * once per vessel until the analyst explicitly regenerates.
 */

import type { AsyncDuckDBConnection } from "@duckdb/duckdb-wasm";

function esc(s: string): string {
  return s.replace(/'/g, "''");
}

export async function initBriefCache(conn: AsyncDuckDBConnection): Promise<void> {
  await conn.query(`
    CREATE TABLE IF NOT EXISTS analyst_briefs (
      mmsi         TEXT PRIMARY KEY,
      brief        TEXT NOT NULL,
      generated_at TIMESTAMP DEFAULT now()
    )
  `);
}

export async function getCachedBrief(
  conn: AsyncDuckDBConnection,
  mmsi: string
): Promise<string | null> {
  try {
    const result = await conn.query(
      `SELECT brief FROM analyst_briefs WHERE mmsi = '${esc(mmsi)}' LIMIT 1`
    );
    const rows = result.toArray();
    if (rows.length === 0) return null;
    return (rows[0].toJSON() as { brief: string }).brief ?? null;
  } catch {
    return null;
  }
}

export async function saveCachedBrief(
  conn: AsyncDuckDBConnection,
  mmsi: string,
  brief: string
): Promise<void> {
  await conn.query(`
    INSERT INTO analyst_briefs (mmsi, brief)
    VALUES ('${esc(mmsi)}', '${esc(brief)}')
    ON CONFLICT (mmsi) DO UPDATE SET brief = excluded.brief, generated_at = now()
  `);
}
