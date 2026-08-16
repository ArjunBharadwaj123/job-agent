import { createClient } from "@libsql/client";

// Shared libSQL (Turso) client. Same database the Python scraper + Gmail scan
// write to. Server-only — never import from a client component.
export const db = createClient({
  url: process.env.TURSO_DATABASE_URL!,
  authToken: process.env.TURSO_AUTH_TOKEN,
});
