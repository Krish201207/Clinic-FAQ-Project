# Clinic FAQ Project

A Flask-based clinic information assistant developed as an educational project. It provides patient accounts, clinic FAQ assistance, appointment booking, doctor information, medicine inventory, billing demonstrations, medical-record handling, and staff dashboards.

## Project links

- **Live application:** https://clinic-faq-project.onrender.com
- **GitHub repository:** https://github.com/Krish201207/Clinic-FAQ-Project
- **Word embeddings reference (Kaggle GloVe):** https://www.kaggle.com/datasets/pkugoodspeed/nlpword2vecembeddingspretrained/data?select=glove.6B.100d.txt

## Main features

- Patient registration and sign-in.
- Chat assistant for clinic FAQs and doctor information.
- Natural-language appointment booking. The assistant gathers missing details, checks doctor availability, and confirms after a booking is saved.
- View and cancel appointments.
- Medicine inventory with 60+ fictional sample items, medicine forms, stock status, and supplier purchase records that update stock.
- Doctor directory with specialty, qualifications, experience, profile summary, certifications, consultation hours, and fees.
- Due-bill tracking with a scannable test-payment QR. Test confirmations are stored as `Paid - Test`; this is not a real payment gateway.
- Staff emergency-case registration and an India emergency call link (112). The app does not dispatch emergency services.
- Account-specific chat history.
- Medical-record metadata and attachments for permitted staff roles.
- Admin/reception analytics and CSV reports.

## AI and NLP components

The project uses two distinct components:

1. **Clinic text classifier** (`clinic_classifier.py`): normalizes and tokenizes a question, looks up known word vectors from `Embeddings.vec`, averages the available vectors into a sentence representation, normalizes that representation, and applies a linear classifier with softmax scores. It assigns one of three categories: `ROUTINE`, `SENSITIVE`, or `UNSUPPORTED`.
2. **Gemini integration** (`app.py`): the application can use the Google Gemini API for generated assistant responses when `GEMINI_API_KEY` is configured. The model defaults to `gemini-2.5-flash`; `GEMINI_MODEL` can override it.

These components have different roles. The word embeddings and classifier weights are local project assets; Gemini is an external API integration.

### NLP files

- `clinic_classifier.py`: text normalization, tokenization, embedding lookup, sentence-vector construction, and classification.
- `Embeddings.vec`: word-vector file loaded by the classifier. Its header supplies the vocabulary size and vector dimension expected by the loader.
- `classifier_weights.txt`: linear classifier parameters. Their shape must match the embedding dimension and the three output labels.
- `FAQ.txt`: clinic FAQ knowledge-base content used by the application; it should not be described as the classifier's labeled training dataset unless a separate training process confirms that.
  
**Embedding compatibility note:** The linked Kaggle resource is GloVe 6B 100-dimensional data. Do not replace the repository's `Embeddings.vec` with `glove.6B.100d.txt` without checking compatibility and regenerating `classifier_weights.txt` for the same vector dimension. The classifier reads the dimension from the embedding file, while the weight matrix must have a matching shape.

The repository documentation does not currently establish the original labeled training dataset, its source/size, the train/test split, or verified classifier evaluation scores. Do not report accuracy, precision, recall, F1-score, or model-comparison results without running an evaluation on a documented labeled test set.

## Technology stack

- Python and Flask
- NumPy
- SQLite for the application's local database
- PostgreSQL/Supabase integration for selected persistent data when `DATABASE_URL` is configured
- Google Gemini API integration through `google-genai`
- HTML, CSS, and JavaScript for the web interface
- Gunicorn and Render for deployment

SQLite remains in use for much of the application's data. The PostgreSQL integration should not be interpreted as a complete migration of every table and feature to PostgreSQL.

## Run locally

1. Install Python 3.10 or later.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. Set a strong `SECRET_KEY` (at least 32 characters). Set `GEMINI_API_KEY` to enable Gemini responses. Configure `DATABASE_URL` if using the supported PostgreSQL persistence features.
6. Start the application:

   ```bash
   python app.py
   ```

The SQLite database is initialized by the application. Keep the required model files (`Embeddings.vec` and `classifier_weights.txt`) alongside the Python source files.

## Important environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session/security key; use a long random value |
| `GEMINI_API_KEY` | Enables Gemini API responses |
| `GEMINI_MODEL` | Optional Gemini model override; default is `gemini-2.5-flash` |
| `DATABASE_URL` | Optional PostgreSQL connection string for supported persistence features |

Never commit a real `.env` file, API keys, database passwords, or other secrets.

## Deployment notes

- The project is configured for deployment on Render.
- Set a stable `SECRET_KEY` in the Render environment.
- Set `GEMINI_API_KEY` if Gemini responses are required.
- Configure `DATABASE_URL` if the supported PostgreSQL persistence features are required.
- The local SQLite database and uploaded files need persistent storage. Render's ephemeral filesystem can lose local files on redeploy unless a persistent disk or external storage is configured.
- Sample doctors, schedules, inventory, and prices are fictional demonstration data.

## Demo staff accounts

The repository includes demonstration credentials for local/project evaluation. They are not production credentials. Change or remove them before any public deployment; never reuse them for real accounts.

## Safety, privacy, and limitations

This is an educational prototype, not a production clinical system. It does not diagnose conditions, prescribe medicines, recommend dosages, or interpret medical reports. The medicine catalogue and clinic records contain fictional demonstration data. The emergency workflow records a case and provides an emergency call link; it does not contact or dispatch emergency services. The payment QR is a test workflow and does not initiate or verify a bank transfer.

A security, privacy, clinical, and operational review is required before any real-world deployment.

## Repository cleanup checklist

Before submission, verify that the repository contains the required source files, templates, static assets, FAQ and model files, and dependency list. Remove caches, temporary files, local databases containing personal data, uploaded test files, and secrets. Do not remove `Embeddings.vec` or `classifier_weights.txt` because the classifier depends on them.
