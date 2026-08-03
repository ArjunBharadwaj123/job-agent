// Minimal Gemini client for on-demand job enrichment. Uses the REST API so
// there's no SDK dependency. Returns a compact, structured enrichment object.

const MODEL = process.env.GEMINI_MODEL || "gemini-2.0-flash";

export interface Enrichment {
  summary: string; // 1-2 sentence role summary
  company_summary: string; // 1-2 sentence company description
  skills: string[]; // key skills / technologies
}

const SYSTEM = `You summarize job postings for a candidate's tracking dashboard.
Return ONLY compact JSON (no markdown) with keys:
- "summary": 1-2 plain sentences describing the role and what it involves.
- "company_summary": 1-2 plain sentences on what the company does.
- "skills": array of 4-10 short skill/technology strings the role wants.
Base "summary" and "skills" on the posting text when provided. If the posting
text is missing, infer conservatively from the title and say nothing you can't
support. Base "company_summary" on well-known facts about the company.`;

export async function enrichJob(input: {
  company: string;
  title: string;
  location?: string | null;
  description?: string | null;
}): Promise<Enrichment | null> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) return null;

  const posting = (input.description || "").slice(0, 6000);
  const prompt = `${SYSTEM}

Company: ${input.company}
Title: ${input.title}
Location: ${input.location || "—"}
Posting text: ${posting || "(none provided)"}`;

  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.3, responseMimeType: "application/json" },
        }),
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    const text: string | undefined =
      data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) return null;
    const parsed = JSON.parse(text);
    return {
      summary: String(parsed.summary || "").trim(),
      company_summary: String(parsed.company_summary || "").trim(),
      skills: Array.isArray(parsed.skills)
        ? parsed.skills.map((s: unknown) => String(s)).slice(0, 12)
        : [],
    };
  } catch {
    return null;
  }
}
