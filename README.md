# CV Insights and Candidate Assessment Tool 

A small web app that parses PDF resumes with an LLM, produces a structured report (education, skills, work experience), computes experience analysis (per-job and total experience with overlap handling), and generates an AI assessment (strengths / weaknesses / red flags / recommendations).
Frontend is a React app. Backend is a Flask API that calls the OpenAI API (GPT-4o) via `resumeparser.py`.

---

## Contents

* `app.py` — Flask backend (POST `/api/process`)
* `resumeparser.py` — Parser + experience analysis + GPT assessment
* `__DATA__/` — upload folder (created automatically)
* `frontend/` — React frontend (replace `src/App.jsx` with provided component)
* `config.yaml` — your (optional) OpenAI key storage (backend fallback)

---

## Requirements

### System

* Python 3.9+
* Node.js 18+ / npm or pnpm / yarn

### Python packages

Install in a virtualenv:

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
venv\Scripts\activate      # Windows
pip install -U pip
pip install flask pypdf flask-cors pyyaml openai
```

> Note: the project uses the official `openai` Python package as `from openai import OpenAI`. If you use a different package version adapt accordingly.

### Frontend packages

From the `frontend` folder:

```bash
cd frontend
npm install
# packages required (example):
# npm i react react-dom recharts jspdf html2canvas
# If you used Vite or CRA scaffolding, make sure tailwind is set up if using tailwind classes.
npm run dev    # or npm start
```

If your frontend requires Tailwind, ensure Tailwind is installed and configured. The provided `App.jsx` uses Tailwind classes.

---

## Setup

### 1) Backend: config.yaml (optional)

You can either give the OpenAI API key per-request from the frontend (the app sends it in header `x-openai-key`) or store a fallback key in the backend config file.

Create `config.yaml` in the backend project root:

```yaml
OPENAI_API_KEY: "sk-...."   # optional fallback; do not commit this file to git
```

If you do not provide `config.yaml`, the frontend must send the key in the header `x-openai-key`.

### 2) Start Flask backend

From project root (where `app.py` and `resumeparser.py` live):

```bash
python app.py
```

You should see something like:

```
* Running on http://0.0.0.0:8000
```

Make sure `UPLOAD_PATH` (`__DATA__`) exists. `app.py` creates it automatically.

### 3) Start frontend

From `frontend/`:

```bash
npm run dev    # or `npm start` depending on your setup
```

Open the frontend dev URL shown by the tooling (commonly `http://localhost:5173` for Vite or `http://localhost:3000` for CRA).

---

## How to use

1. Open the frontend in browser.
2. Click **Choose File** and select a PDF resume.
3. Paste your OpenAI API key into the key box (starts with `sk-...`) — or ensure `config.yaml` contains a valid key.
4. Click **Process**.
5. The parsed report, experience pie chart, and AI assessment appear. Use **Download JSON** / **Download PDF** to save results.

---

## API

**POST** `/api/process`

* Content-Type: `multipart/form-data`
* Field: `pdf_doc` — PDF file to parse
* Optional header: `x-openai-key` — per-request OpenAI key (if not using `config.yaml`)

Example `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/process" \
  -H "x-openai-key: sk-..." \
  -F "pdf_doc=@/path/to/resume.pdf"
```

Response JSON:

```json
{
  "success": true,
  "result": { ... parsed dict ... }
}
```

`result` is a dict containing:

* `full_name`, `email`, `github`, `linkedin`
* `employment_details` (array of jobs)
* `technical_skills`, `soft_skills`, `education`, `languages`, `certifications`
* `experience_analysis` (per-job durations, merged total)
* `assessment` (strengths, weaknesses, red_flags, recommendations, overall_score)

---

## Notes on `resumeparser.py` behavior

* Uses GPT-4o (model name `gpt-4o` in prompts). Change model name in `resumeparser.py` if you want to use a different model.
* The parser attempts to return **strict JSON**. The code includes robust cleaning and JSON-fix logic to handle model output variance.
* `ats_extractor(resume_text, api_key=None)` accepts an optional `api_key`. If you pass an API key from the frontend in header `x-openai-key`, that key will be used for the model calls; otherwise the backend will use `config.yaml` if present.
* Experience analysis:

  * Parses fuzzy dates like `Jan 2022`, `Aug 2019 – May 2023`, and `Present`.
  * Computes per-job duration in months and a human-readable format.
  * Merges overlapping intervals to compute total experience (days/months/years approximated).
* Assessment generation calls the LLM to produce a JSON-only assessment (strengths/weaknesses/red_flags/recommendations/overall_score).

---

## Troubleshooting

### `Failed to fetch` or CORS errors

* Ensure Flask is running on the port your frontend calls (default `8000`).
* Make sure `app.py` includes `CORS(app)` and you restarted Flask after changes.
* Check browser console (Network tab) for:

  * `net::ERR_CONNECTION_REFUSED` — backend not running or wrong port
  * `Access-Control-Allow-Origin` missing — CORS not enabled on backend

### Backend returns text instead of JSON

* The frontend will try to parse model output. If the model returns non-JSON text, it may be wrapped under `raw_output` in `result`.
* Improve parsing reliability by editing the extraction prompt inside `resumeparser.py` and adding more few-shot examples.

### High token usage / cost

* GPT-4o calls with large PDFs can be costly. Consider:

  * Pre-processing: extract only textual parts relevant to parsing.
  * Chunking large documents and sending only relevant chunks to the model.
  * Using a smaller model (e.g., `gpt-3.5-turbo`) for the extraction phase if acceptable.

---

## Security & privacy

* **Do not commit** `config.yaml` containing your API key to version control.
* When using the web UI, the provided OpenAI key is sent from the browser to your backend in the header `x-openai-key`. The backend uses the key for the OpenAI call and does not store it (unless you change code to persist).
* If you deploy this publicly, replace the user-key flow with a secure server-side key management or require user authentication. Do not expose your backend key to arbitrary clients.

---

## Customization ideas / next steps

* Make `education` a structured array of objects `{ degree, institution, start_year, end_year }`.
* Add pagination for very long parsed results.
* Add an "explain" button that asks the LLM to justify the assessment in plain English (keeps both JSON and text).
* Cache parsing results for repeated uploads of the same file to reduce cost.
* Add unit tests around date parsing (fuzzy date parsing functions).

---

## Example `config.yaml` (do NOT commit)

```yaml
OPENAI_API_KEY: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```


