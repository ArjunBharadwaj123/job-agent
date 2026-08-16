import { createHash } from "crypto";

// Port of the scraper's generate_job_id (src/sheet_reader.py) so a manually
// added job shares the same deterministic id as the scraped one — letting the
// daily scraper upsert instead of duplicating. Must stay in lockstep with the
// Python normalization.

// Python uses re.sub(r"[^\w\s]", ...) with the default UNICODE flag, i.e.
// remove anything that isn't a Unicode letter/number/underscore or whitespace.
const PUNCT = /[^\p{L}\p{N}_\s]/gu;
const WS = /\s+/g;

export function normalizeText(text: string): string {
  if (!text) return "";
  return text.toLowerCase().replace(PUNCT, "").replace(WS, " ").trim();
}

const LEGAL_SUFFIXES = new Set([
  "inc", "incorporated", "llc", "ltd", "limited",
  "corp", "corporation", "co", "company",
]);

export function normalizeCompany(company: string): string {
  if (!company) return "";
  const cleaned = company.toLowerCase().replace(PUNCT, "");
  return cleaned
    .split(/\s+/)
    .filter((w) => w && !LEGAL_SUFFIXES.has(w))
    .join(" ")
    .trim();
}

export function generateJobId(company: string, title: string, location: string): string {
  const identity = `${normalizeCompany(company)}|${normalizeText(title)}|${normalizeText(location)}`;
  return createHash("sha256").update(identity, "utf-8").digest("hex");
}
