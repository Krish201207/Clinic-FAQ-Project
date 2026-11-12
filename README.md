# Hospital Management + AI Patient Assistant (Flask demo)

This package extends the existing Flask Clinic FAQ concept with six working demo modules: appointments, doctor availability, patient query analytics, billing, health-record metadata/file uploads, and medicine prices/inventory. The Gemini FAQ assistant and existing optional `clinic_classifier.py` are retained as optional integrations.

## Run locally

1. Put this folder alongside the existing project files `FQA.txt`, `clinic_classifier.py`, `Embeddings.vec`, and `classifier_weights.txt` if you want to reuse the clinic FAQ and classifier. The app still starts without the classifier files; Gemini requires `GEMINI_API_KEY`.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`, generate a unique secret with `python -c "import secrets; print(secrets.token_hex(32))"`, and put that value in `SECRET_KEY`. Do not commit a real API key or `.env` file.
5. Run: `python app.py`
6. Open `http://127.0.0.1:5000`.

The database `hospital.db` is created automatically on first run. The included `FQA.txt` is copied from your existing clinic project; review and update its clinic-specific details before treating it as hospital information.

## Demo staff accounts

- Admin: `admin@demo.local` / `admin123`
- Reception: `reception@demo.local` / `reception123`
- Doctor: `doctor@demo.local` / `doctor123`

Patients can register through the registration page. These staff accounts and the seeded doctors/medicines are demo data. Change or remove demo accounts before deployment.

## Roles

- Patient: book/cancel own appointments; view own bills and health records; use the chatbot and medicine catalogue.
- Doctor: view appointments and records; add health-record entries.
- Reception: view appointments, create bills, manage demo medicine entries, and view query analytics.
- Admin: reception capabilities plus administrative access to records and analytics.

## Important limitations

This is an educational prototype, not a production hospital information system. It has basic login and role checks but does not implement production-grade account recovery, MFA, audit trails, CSRF protection, encryption/key management, consent workflows, payment-gateway integration, verified pharmacy/doctor data, or regulatory compliance. Do not enter real patient data or deploy it for real clinical use without a security and privacy review. Uploaded files are stored locally in `uploads/`; configure persistent private storage and backups before deployment. The sample doctor schedules, medicine prices, and stock values are fictional demo data. Billing marks a bill as paid for demonstration only; it does not process payments.

## Existing project compatibility

The existing `FQA.txt` is included. To restore classifier metadata, copy your working `clinic_classifier.py`, `Embeddings.vec`, and `classifier_weights.txt` into this folder. The classifier is used only as query-history metadata and never blocks the Gemini request. If Gemini is not configured, the other hospital modules continue to work and the chatbot reports that the API key is missing.


## Session/login fix and dashboard layout

The dashboard now explicitly sends same-origin session cookies with API calls. The modules are arranged in a left sidebar with the selected module displayed in the main workspace. Keep `SECRET_KEY` stable across restarts and all workers; if it changes, existing sessions become invalid. Set a long random `SECRET_KEY` in production. For HTTPS deployment set `COOKIE_SECURE=1`. If a 401 persists, inspect the failing `/api/...` request in browser developer tools and verify the Flask session cookie is present; do not share the cookie value.


### Individual doctor demo logins

- `doctor0@demo.local` / `00000000`
- `doctor1@demo.local` / `00000001`
- `doctor2@demo.local` / `00000002`

These are fixed demonstration credentials, not secure production passwords. Each account is assigned to one of the first three doctor profiles and sees appointments for that assigned doctor and health records it created. Admin and reception users can download a CSV summary report from **Reports & analytics**.

## Executive dashboard additions
- Premium navy-and-gold visual theme with responsive left navigation and workspace layout.
- Live dashboard KPI cards for appointments, active doctors, unpaid bills, and (for admin/reception) chatbot queries.
- Workspace-wide search filters visible module cards and list entries.
- Appointment status filter (all, booked, cancelled).
- Dark mode toggle (saved in the current browser), current date/time display, and print-current-view control.
- Quick appointment shortcut and report export shortcut for admin/reception.

These are interface and workflow enhancements for the educational demo. Sample data is not real hospital data, and this is not a production-ready clinical information system.

## Registration and login reliability updates

- Patient registration now asks for **name, email, and password only**. The legacy `phone` database column is left in place so existing `hospital.db` files remain compatible; the registration form no longer collects or writes a phone number.
- Passwords continue to be stored as Werkzeug password hashes.
- On a local installation, the Flask session secret is generated once and stored in `instance/.secret_key`. Keep the `instance` folder when moving/restarting the project. It is excluded from Git because it contains a secret.
- On hosting platforms, set a stable `SECRET_KEY` environment variable (at least 32 characters) in the hosting dashboard. Do not rely on the generated local key on ephemeral or multi-instance hosts.
- `HOSPITAL_DB_PATH` selects the exact SQLite database file. Keep it pointed at the same persistent file across deploys. On Render, mount a persistent disk and use a path such as `/var/data/hospital.db`; copy your existing `hospital.db` to that disk once before switching the setting.
- For HTTPS hosting, set `COOKIE_SECURE=1`. Leave it unset/`0` for local `http://127.0.0.1:5000`, otherwise browsers will not send the secure cookie over plain HTTP.
- The application uses a named session cookie, a 14-day refreshable session, SQLite WAL mode, and a longer SQLite busy timeout. These reduce common session and concurrent-write failures but do not make an ephemeral database persistent.

### Login troubleshooting

1. Check `/health` and confirm `database_exists` is `true` and the `database` path is the intended file.
2. If the browser gets HTTP 401 from an API after login, verify the browser is keeping the `greenfield_session` cookie and that all app workers share the same `SECRET_KEY`.
3. If login works but patient data disappears after redeploy, the SQLite file is on ephemeral storage. Configure persistent storage and migrate the existing database; changing the session key does not fix database loss.
4. Do not delete `hospital.db`, `instance/.secret_key`, or the persistent disk contents when updating application code.

### UI and interaction updates

The clinical dashboard uses distinct department color accents, colored service tiles, layered panels, and optional dark mode. The refresh, dark-mode, print, navigation, quick-chat, form-submit, appointment-cancel, bill-payment, and report-download controls have actions. Modules not permitted for a role are hidden from that role's navigation and protected by the API.

**Verification limitation:** Python compilation and JavaScript syntax checks were run. A live Flask/browser integration test could not be run in this environment because Flask is not installed and package installation is unavailable.


## Chat assistant actions

The Patient Help Desk routes supported commands to database operations before asking the FAQ/AI layer.
Examples:
- `Book an appointment with Dr. Asha Mehta tomorrow at 10 AM`
- `Book appointment with cardiologist at 5 PM` (the assistant asks for any missing date)
- `Show my appointments`
- `Cancel appointment #12`
- `Show available doctors`
- `Show the hospital price list`
- `Find paracetamol`
- `Show my bills`
- Reception/admin: `Create bill for patient ID 5 amount 750 description consultation`

The assistant only confirms a booking after the database insert succeeds. It checks doctor schedule, future date, working hours, and duplicate doctor/time slots. If a booking is incomplete, it asks for missing details. An unrelated request no longer gets trapped in an unfinished booking flow.

The login page no longer displays demonstration account credentials. Keep test credentials in a private deployment note, not on the public sign-in screen.

The doctor schedules, prices, and medicine stock are sample data and must be replaced with verified hospital data before real use. This is a demonstration system, not a production clinical system.
