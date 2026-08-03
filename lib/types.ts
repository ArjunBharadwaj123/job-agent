// Shared types + the application-status vocabulary for the dashboard.

export type ApplicationStatus =
  | "not_applied"
  | "applied"
  | "pending"
  | "assessment"
  | "interview"
  | "rejected"
  | "accepted";

// Ordered pipeline (drives the stepper + kanban ordering).
export const STATUS_ORDER: ApplicationStatus[] = [
  "not_applied",
  "applied",
  "pending",
  "assessment",
  "interview",
  "accepted",
  "rejected",
];

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  not_applied: "Not applied",
  applied: "Applied",
  pending: "Pending",
  assessment: "Assessment",
  interview: "Interview",
  rejected: "Rejected",
  accepted: "Accepted",
};

// Tailwind classes for status chips (light + dark aware via the base palette).
export const STATUS_STYLES: Record<ApplicationStatus, string> = {
  not_applied: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  applied: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  pending: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  assessment: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  interview: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  rejected: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
  accepted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
};

export interface Job {
  job_id: string;
  job_title: string;
  company: string;
  location: string | null;
  job_url: string | null;
  source: string | null;
  date_posted: string | null;
  date_found: string | null;
  relevance_score: number | null;
  role_type: string | null;
  confidence: number | null;
  semantic_scored: number;
  archived: number;
  last_updated: string | null;
  locked: number;
  applied: number;
  date_applied: string | null;
  application_status: ApplicationStatus;
  priority: string | null;
  notes: string | null;
  action_type: string | null;
  action_url: string | null;
  description: string | null;
  summary: string | null;
  company_summary: string | null;
  skills: string | null;
  enriched_at: string | null;
}

export interface StatusEvent {
  id: number;
  job_id: string;
  old_status: string | null;
  new_status: string | null;
  source: string | null;
  email_id: string | null;
  email_thread_url: string | null;
  confidence: number | null;
  reasoning: string | null;
  action_type: string | null;
  action_url: string | null;
  needs_review: number;
  created_at: string | null;
}

export const PRIORITIES = ["", "low", "medium", "high"] as const;
export type Priority = (typeof PRIORITIES)[number];
