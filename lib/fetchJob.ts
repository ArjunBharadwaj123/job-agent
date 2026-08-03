// Best-effort fetch of a job posting's visible text, used to enrich a job the
// scraper didn't store a description for. Prefers schema.org JobPosting
// JSON-LD, falls back to stripped body text. Returns "" on any failure.

export async function fetchJobText(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        Accept: "text/html",
      },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return "";
    const html = await res.text();

    // 1) Try JSON-LD JobPosting.description
    const ld = extractJsonLdDescription(html);
    if (ld) return stripHtml(ld).slice(0, 8000);

    // 2) Fall back to the whole body, stripped.
    return stripHtml(html).slice(0, 8000);
  } catch {
    return "";
  }
}

function extractJsonLdDescription(html: string): string | null {
  const blocks = html.match(
    /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  );
  if (!blocks) return null;
  for (const block of blocks) {
    const json = block.replace(/<[^>]+>/g, "");
    try {
      const data = JSON.parse(json);
      const nodes = Array.isArray(data) ? data : [data];
      for (const node of nodes) {
        if (node && (node["@type"] === "JobPosting" || node.description)) {
          if (typeof node.description === "string") return node.description;
        }
      }
    } catch {
      // ignore malformed JSON-LD
    }
  }
  return null;
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#\d+;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
