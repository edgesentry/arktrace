/**
 * Analyst chat history — persisted in DuckDB (OPFS-backed).
 *
 * Table: analyst_chat_history(id, mmsi, role, content, created_at)
 * One row per message turn; loaded on vessel select, survives page reload.
 */

import type { AsyncDuckDBConnection } from "@duckdb/duckdb-wasm";

export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  id: string;
  mmsi: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

function esc(s: string): string {
  return s.replace(/'/g, "''");
}

export async function initChatSchema(conn: AsyncDuckDBConnection): Promise<void> {
  await conn.query(`
    CREATE TABLE IF NOT EXISTS analyst_chat_history (
      id         TEXT PRIMARY KEY,
      mmsi       TEXT NOT NULL,
      role       TEXT NOT NULL,
      content    TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT now()
    )
  `);
}

export async function loadChatHistory(
  conn: AsyncDuckDBConnection,
  mmsi: string
): Promise<ChatMessage[]> {
  try {
    const result = await conn.query(
      `SELECT id, mmsi, role, content, CAST(created_at AS VARCHAR) AS created_at
       FROM analyst_chat_history
       WHERE mmsi = '${esc(mmsi)}'
         AND role != 'system'
       ORDER BY created_at ASC`
    );
    return result.toArray().map((r) => r.toJSON() as ChatMessage);
  } catch {
    return [];
  }
}

export async function appendChatMessage(
  conn: AsyncDuckDBConnection,
  mmsi: string,
  role: ChatRole,
  content: string
): Promise<void> {
  const id = crypto.randomUUID();
  await conn.query(`
    INSERT INTO analyst_chat_history (id, mmsi, role, content)
    VALUES ('${esc(id)}', '${esc(mmsi)}', '${esc(role)}', '${esc(content)}')
  `);
}

export async function clearChatHistory(
  conn: AsyncDuckDBConnection,
  mmsi: string
): Promise<void> {
  await conn.query(`DELETE FROM analyst_chat_history WHERE mmsi = '${esc(mmsi)}'`);
}
