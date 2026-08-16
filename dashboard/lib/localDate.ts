// The browser's local calendar date as YYYY-MM-DD. Sent with status updates so
// date_applied reflects the user's timezone, not the server's UTC.
export function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
