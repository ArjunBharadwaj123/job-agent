"use client";

import { useEffect, useState } from "react";

// Renders a UTC ISO timestamp in the viewer's local timezone. Formatting must
// happen on the client (via useEffect) so it uses the browser's zone rather
// than the server's UTC — and so the hydration output matches the server's.
export default function LocalTime({ iso }: { iso: string | null }) {
  const [text, setText] = useState("");

  useEffect(() => {
    if (!iso) return;
    setText(
      new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    );
  }, [iso]);

  if (!iso) return null;
  // Server + first client render show the date (deterministic); the effect then
  // fills in the local date+time.
  return <span suppressHydrationWarning>{text || iso.slice(0, 10)}</span>;
}
