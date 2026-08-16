// Keyless company blurb via Wikipedia's free REST summary API.
// Returns a 1-2 sentence extract, or null when there's no clean match.

export async function wikiSummary(company: string): Promise<string | null> {
  const candidates = [company, `${company} (company)`];
  for (const name of candidates) {
    const extract = await fetchOne(name);
    if (extract) return extract;
  }
  return null;
}

async function fetchOne(title: string): Promise<string | null> {
  try {
    const res = await fetch(
      `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}?redirect=true`,
      { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(6000) }
    );
    if (!res.ok) return null;
    const data = await res.json();
    if (data.type === "disambiguation") return null;
    const extract: string | undefined = data.extract;
    if (!extract || extract.length < 20) return null;
    // Keep it short: first two sentences.
    const sentences = extract.match(/[^.!?]+[.!?]+/g) || [extract];
    return sentences.slice(0, 2).join(" ").trim();
  } catch {
    return null;
  }
}
