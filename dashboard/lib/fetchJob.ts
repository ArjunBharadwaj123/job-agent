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

export interface ParsedJob {
  title: string;
  company: string;
  location: string;
  description: string;
}

// Pull a full JobPosting from a URL's schema.org JSON-LD (best-effort; fields
// are "" when the page blocks the fetch or lacks structured data).
export async function extractJobPosting(url: string): Promise<ParsedJob> {
  const empty: ParsedJob = { title: "", company: "", location: "", description: "" };
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        Accept: "text/html",
      },
      signal: AbortSignal.timeout(9000),
    });
    if (!res.ok) return empty;
    const html = await res.text();
    const node = findJobPostingNode(html) ?? {};
    // Prefer JSON-LD; fall back to og:/<title> meta tags for pages that don't
    // expose a full JobPosting (e.g. Greenhouse boards).
    let title = str(node.title) || meta(html, "og:title") || titleTag(html);
    let company = orgName(node.hiringOrganization) || meta(html, "og:site_name");
    let location = jobLocation(node.jobLocation);
    // LinkedIn og:title format: "{Company} hiring {Title} in {Location} | LinkedIn"
    const li = title.match(/^(.+?) hiring (.+?) in (.+?)\s*\|\s*LinkedIn/i);
    if (li) {
      if (!company) company = li[1].trim();
      title = li[2].trim();
      if (!location) location = li[3].trim();
    }
    const description = node.description
      ? stripHtml(str(node.description)).slice(0, 8000)
      : stripHtml(html).slice(0, 8000);
    return { title, company, location, description };
  } catch {
    return empty;
  }
}

function str(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function decode(s: string): string {
  return s
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").trim();
}

function meta(html: string, prop: string): string {
  const re = new RegExp(
    `<meta[^>]+(?:property|name)=["']${prop}["'][^>]+content=["']([^"']+)["']`,
    "i"
  );
  const m = html.match(re) || html.match(
    new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']${prop}["']`, "i")
  );
  return m ? decode(m[1]) : "";
}

function titleTag(html: string): string {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? decode(m[1]).replace(/\s+/g, " ") : "";
}

function orgName(org: unknown): string {
  if (typeof org === "string") return org.trim();
  if (org && typeof org === "object" && "name" in org) return str((org as { name: unknown }).name);
  return "";
}

function jobLocation(loc: unknown): string {
  const first = Array.isArray(loc) ? loc[0] : loc;
  const addr = first && typeof first === "object" ? (first as { address?: unknown }).address : undefined;
  if (!addr || typeof addr !== "object") return "";
  const a = addr as { addressLocality?: unknown; addressRegion?: unknown };
  return [str(a.addressLocality), str(a.addressRegion)].filter(Boolean).join(", ");
}

// Scan all JSON-LD blocks (including @graph arrays) for a JobPosting node.
function findJobPostingNode(html: string): Record<string, unknown> | null {
  const blocks = html.match(
    /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  );
  if (!blocks) return null;
  for (const block of blocks) {
    const json = block.replace(/^<[^>]*>/, "").replace(/<\/script>\s*$/i, "");
    try {
      const data = JSON.parse(json);
      const nodes: unknown[] = [];
      const push = (d: unknown) => {
        if (Array.isArray(d)) d.forEach(push);
        else if (d && typeof d === "object") {
          nodes.push(d);
          if ("@graph" in d) push((d as { "@graph": unknown })["@graph"]);
        }
      };
      push(data);
      for (const n of nodes) {
        const node = n as Record<string, unknown>;
        const t = node["@type"];
        if (t === "JobPosting" || (Array.isArray(t) && t.includes("JobPosting"))) {
          return node;
        }
      }
    } catch {
      // ignore malformed JSON-LD
    }
  }
  return null;
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
