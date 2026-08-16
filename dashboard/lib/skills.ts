// Keyless skill extraction: match a curated dictionary against posting text.
// Not as nuanced as an LLM, but free and deterministic. The canonical label
// (value) is shown; the regex-safe key is what we match.

const SKILLS: [label: string, pattern: RegExp][] = (
  [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "Ruby",
    "Scala", "Kotlin", "Swift", "PHP", "Perl", "MATLAB", "R",
    ["C++", /c\+\+/i], ["C#", /c#|\.net|dotnet/i],
    // Single-letter langs: require nearby context to avoid stray matches.
    ["C", /\bc\b(?=\s*[/,)]|\s+programming|\s+language)/i],
    ["R", /\br\b(?=\s*[/,)]|\s+programming|\s+language|\s+studio)/i],
    "React", "Angular", "Vue", ["Node.js", /node(\.js)?/i], "Next.js",
    "Django", "Flask", "FastAPI", "Spring", "Express", "Rails",
    "TensorFlow", "PyTorch", ["scikit-learn", /scikit-?learn|sklearn/i],
    "Pandas", "NumPy", "Spark", "Hadoop", "Kafka", "Airflow", "Databricks",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    ["CI/CD", /ci\/cd|continuous integration/i], "Ansible",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Snowflake", "DynamoDB",
    "Elasticsearch", "GraphQL", ["REST", /\brest(ful)?\b/i], "gRPC",
    ["Machine Learning", /machine learning|\bml\b/i],
    ["Deep Learning", /deep learning/i], ["NLP", /\bnlp\b|natural language/i],
    ["LLMs", /\bllms?\b|large language model/i],
    ["Distributed Systems", /distributed systems?/i],
    ["Microservices", /micro-?services?/i], "Kubernetes",
    ["Data Structures", /data structures/i], ["Algorithms", /algorithms?/i],
    "Linux", "Git", "Agile", "Scala", "Tableau", "Kotlin",
  ] as (string | [string, RegExp])[]
).map((s) =>
  typeof s === "string"
    ? [s, new RegExp(`\\b${s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i")]
    : s
);

export function extractSkills(text: string, max = 10): string[] {
  if (!text) return [];
  const found: string[] = [];
  const seen = new Set<string>();
  for (const [label, pattern] of SKILLS) {
    if (seen.has(label)) continue;
    if (pattern.test(text)) {
      found.push(label);
      seen.add(label);
    }
    if (found.length >= max) break;
  }
  return found;
}

// A short "brief" of the posting: first couple of sentences, trimmed. Skips
// common site nav/chrome (LinkedIn/Indeed) by starting at a description marker
// when one is present.
const DESC_MARKER =
  /about the (job|role)|job description|the role|role overview|what you.?ll do|responsibilities|who we are|overview|about the team|the opportunity/i;

export function briefFromText(text: string, maxChars = 320): string {
  if (!text) return "";
  let clean = text.replace(/\s+/g, " ").trim();
  const markerIdx = clean.search(DESC_MARKER);
  if (markerIdx > 0 && markerIdx < clean.length - 80) {
    clean = clean.slice(markerIdx);
  }
  const sentences = clean.match(/[^.!?]+[.!?]+/g) || [clean];
  let out = "";
  for (const s of sentences) {
    if ((out + s).length > maxChars && out) break;
    out += s;
    if (out.length >= maxChars) break;
  }
  return (out || clean).slice(0, maxChars + 60).trim();
}
