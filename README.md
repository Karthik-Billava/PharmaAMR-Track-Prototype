# PharmaAMR-Track — Android-compatible multi-pharmacy prototype

A mobile-first Progressive Web App (PWA) for community-pharmacy antimicrobial-use (AMU) data collection. It is a demonstration prototype, not a validated national surveillance product.

## Included
- Responsive Android-friendly web interface and installable PWA shell
- Central database architecture (PostgreSQL for deployment; SQLite for quick local demo)
- Separate pharmacy accounts and pharmacy-level record isolation
- Network administrator dashboard with aggregated pharmacy records
- Patient-interaction and antibiotic dispensing data form
- AWaRe category summaries, CSV export, basic transparent pattern alerts
- Audit log for record creation
- Fictional demo accounts and data environment

## Run locally (quick demo)
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

SQLite database file `pharmaamr_demo.db` is created automatically.

## Demo logins
- Network administrator: `admin` / `Admin@12345`
- Pharmacy 1: `pharmacy1` / `Pharmacy@123`
- Pharmacy 2: `pharmacy2` / `Pharmacy@123`
- Pharmacy 3: `pharmacy3` / `Pharmacy@123`

Change all demo passwords and the secret key before any deployment. Demo accounts are seeded only when the users table is empty.

## Run centrally with PostgreSQL using Docker
Install Docker Desktop, then:

```bash
docker compose up --build
```

Open http://localhost:8000. Docker Compose starts one PostgreSQL database and the web application. All pharmacy accounts connect to this same central database, while application queries restrict pharmacy users to their own pharmacy records.

**Before internet deployment:** change the PostgreSQL password and `SECRET_KEY`, use HTTPS, set `COOKIE_SECURE=true`, disable demo seeding after initial setup, configure backups, add rate limiting and CSRF protection, review access controls, and have the deployment security-tested.

## Android installation
1. Host the app on an HTTPS domain.
2. Open the domain in Chrome on Android.
3. Open Chrome's menu and choose **Add to Home screen** or **Install app**.
4. Sign in using the pharmacy account assigned by the network administrator.

The PWA caches only static interface assets. It requires an internet connection for sign-in, saving records and viewing the central database. Offline record submission and later synchronization are not implemented in this MVP.

## Data model
- `pharmacies`: participating pharmacy directory
- `users`: administrator and pharmacy accounts
- `visits`: patient-interaction context, prescription status, reported symptoms, prior use and outcome
- `medicine_records`: antibiotic requested/dispensed details and AWaRe category
- `audit_logs`: record creation audit events

One visit stores one antibiotic in this MVP. For a real deployment, extend the form to support multiple antibiotic line-items per visit.

## Important prototype limitations
- Use fictional data only for presentations and testing.
- No patient names, mobile numbers or exact home addresses are collected.
- Patient token is random per visit; longitudinal patient matching is not enabled.
- AI alerts are simple rule-based demonstrations, not trained ML and not validated for outbreak detection.
- AWaRe category is entered by the user in this MVP; connect a verified, versioned drug catalogue before operational use.
- No prescription image/OCR, laboratory AMR linkage, follow-up module, multi-language support, consent workflow or full user-management screen yet.
- It records antimicrobial use/dispensing, not microbiological resistance. Do not infer AMR from pharmacy data alone.
- Obtain legal, privacy, security and ethics review before collecting real patient data. Follow applicable Indian data-protection and pharmacy requirements.

## Suggested next development tasks
1. Admin-only create/deactivate pharmacy and user management.
2. Verified antibiotic catalogue with ATC and WHO AWaRe mappings.
3. Multiple antibiotic line-items per visit.
4. Consent and retention controls, CSRF protection, rate limiting and password reset.
5. Offline draft queue with safe sync and conflict handling.
6. District-level aggregate analytics with small-cell suppression.
7. Validated statistical anomaly detection and laboratory AMR data linkage.
