# Clinic FAQ Project

A Flask-based clinic information assistant with patient accounts, natural-language appointment booking, doctor schedules, chat history, medical records, and a medicine inventory.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Set a strong `SECRET_KEY` (at least 32 characters). Set `GEMINI_API_KEY` to enable Gemini responses.
5. Run `python app.py` and open `http://127.0.0.1:5000`.

The SQLite database is initialized automatically. Existing databases are migrated to add medicine forms and expanded doctor profile fields.

## Main features

- Patient registration and sign-in.
- Chat assistant for clinic FAQ questions and doctor information.
- Natural-language appointment booking. Example: “Book me a cardiologist next Friday before noon.” The assistant asks for missing details, checks the doctor's schedule, chooses an available morning slot, and confirms only after the booking is saved.
- View and cancel appointments.
- Medicine inventory with 60+ fictional sample items, medicine forms, stock status, and supplier purchase records that update stock.
- Doctor directory with specialty, qualifications, experience, professional profile summary, certifications, consultation hours, and fees.
- Due-bill tracking with a payment test QR flow. Test confirmations are stored as `Paid - Test`; this flow is not connected to a payment gateway.
- Staff emergency-case registration and a direct India emergency call link (112). The app does not dispatch emergency services.
- Account-specific chat history.
- Medical record metadata and attachments for permitted staff roles.
- Admin/reception analytics and CSV reports.

The included doctor, medicine, schedule, and price entries are sample records intended for project evaluation. The payment QR is a test workflow and does not initiate or verify a bank transfer.

## Demo staff accounts

- Admin: `admin@demo.local` / `admin123`
- Reception: `reception@demo.local` / `reception123`
- Doctor: `doctor@demo.local` / `doctor123`
- Individual doctor accounts: `doctor0@demo.local` / `00000000`, `doctor1@demo.local` / `00000001`, `doctor2@demo.local` / `00000002`

These are demonstration credentials. Change or remove them before deployment.

## Deployment notes

- Set a stable `SECRET_KEY` in Render environment variables.
- Set `GEMINI_API_KEY` if Gemini answers are required.
- Use persistent storage for the SQLite database and uploaded files. Render's ephemeral filesystem can lose local files on redeploy.
- Sample doctors, schedules, inventory, and prices are fictional demonstration data.

## Safety and limitations

This is an educational prototype, not a production clinical system. The medicine catalogue describes inventory forms and stock only; the assistant does not prescribe medicines, recommend dosages, diagnose conditions, or interpret reports. Do not use sample schedules or inventory for real patient care. A security, privacy, and clinical review is required before any real-world deployment.
