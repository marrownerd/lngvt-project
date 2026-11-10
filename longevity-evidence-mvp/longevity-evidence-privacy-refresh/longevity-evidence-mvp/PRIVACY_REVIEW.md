# Privacy review — local prototype

## Changes in this revision
- Replaced the decorative gradient/card treatment with a restrained editorial research-workspace style.
- Added an in-app Privacy & data page describing local storage, Streamlit session mechanisms, PubMed requests, and deletion.
- Removed topic/condition values from successful collection-run details.
- Replaced raw exception text in collection history with the exception class name.
- Disabled external LLM processing by default unless `ALLOW_EXTERNAL_LLM=1` is explicitly configured.
- Removed age, sex, conditions and interest profile fields from the payload sent to the external LLM.

## Findings and limitations
- SQLite stores the optional profile fields (age, sex, conditions, interests) in plaintext in the local `data/` directory. This is not suitable for a shared/public host without encryption-at-rest, access control and a data-retention design.
- Streamlit uses necessary runtime/session mechanisms. This project does not include an analytics, advertising or cookie-tracking SDK. Verify actual cookies in browser devtools after deployment because hosting/proxy/auth layers can add their own.
- PubMed receives search terms when a user explicitly starts collection. Avoid highly identifying or personal health search strings.
- The Activity page displays local operational records. Keep access to the local host restricted.
- No account system, role-based access, user-level data isolation, deletion request workflow, consent management platform, or processor agreements are implemented.
- No legal guarantee or GDPR compliance certification is made. Public deployment requires a DPIA screening, lawful-basis assessment, transparent controller identity/contact, processor contracts, retention schedule, data-subject rights workflow, hosting-region review and security testing.

## Cookie approach
No non-essential cookies or analytics are intentionally added by this code. A consent banner is therefore not added: it would be misleading to ask for consent to tracking that is not present. If non-essential analytics/marketing/embedded third-party scripts are introduced, they must be blocked until affirmative consent, with equally prominent accept and reject controls and a way to withdraw consent.

## Manual verification before any public deployment
1. Inspect browser DevTools → Application → Cookies and Storage on a clean browser profile.
2. Inspect DevTools → Network for third-party requests before and after using the app.
3. Confirm HTTPS, secure session-cookie flags, CSRF protections and restrictive CORS at the hosting layer.
4. Confirm secrets are server-side only and rotate any key ever committed to Git.
5. Confirm database and backups are encrypted and access-restricted.
