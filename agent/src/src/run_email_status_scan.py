"""
Daily Gmail application-status scan entry point.

Reads recent emails (read-only), matches them to applied jobs in Turso,
classifies the status via Groq (keyword-rules fallback), and updates the DB.
Needs: TURSO_*, GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN, GROQ_API_KEY, NTFY_TOPIC.

Run: PYTHONPATH=src python src/run_email_status_scan.py
"""

import email_scan

if __name__ == "__main__":
    email_scan.main()
