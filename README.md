
# Alert Intelligence Web Application
 
A privacy-first Streamlit dashboard plus FastAPI service for comparing previous-week and current-week alert dumps, discovering common factors, estimating next-week recurrence risk, and exporting Excel/PDF reports.
 
## Features
- Two `.xlsx` upload cards on the landing page, with a Home link back from any analysis
- Alias-based column normalization
- Severity, criticality, group, CI, creation-time, update-time and reopen comparisons
- Description/work-note keyword analysis
- Transparent next-week recurrence risk ranked by alert signature
- Excel and PDF exports
- Docker deployment with no required internet connection at runtime
- REST API and OpenAPI v2 definition for a Microsoft Copilot Studio agent
 
## Quick start

Requires Python 3.11–3.13.

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

**macOS / Linux**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Open `http://localhost:8501`.

### Try it with demo data
The dashboard needs two workbooks before it renders anything. Generate a realistic pair:
```bash
python create_sample_data.py
```
This writes `alerts_previous_week.xlsx` and `alerts_current_week.xlsx` into the project root. Drop them into the two upload cards on the landing page and press **Run analysis**. The demo headers use ServiceNow-style aliases, so they also exercise the column normalizer.

For a blank workbook with the canonical headers instead, run `python create_template.py`.

### Run the API locally
```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```
Interactive docs at `http://localhost:8000/docs`.

### Verify the pipeline without the UI
```bash
python smoke_test.py
```
Exercises normalization, comparison, keywords, forecasting and both exports against the sample data.
 
## Docker deployment
```bash
docker compose up --build -d
```
Dashboard: `http://SERVER:8501`  
API: `http://SERVER:8000`  
API docs: `http://SERVER:8000/docs`
 
## Expected workbook columns
`alert_id`, `severity`, `criticality`, `assignment_group`, `configuration_item`, `created_at`, `updated_at`, `reopened`, `description`, `work_notes`.
 
Common ServiceNow-style aliases are recognized. Edit `CANONICAL` in `analysis_engine.py` for organization-specific headers.
 
## Copilot Studio agent
1. Deploy the API behind an approved internal HTTPS reverse proxy.
2. Replace `REPLACE_WITH_INTERNAL_API_HOST` in `copilot/openapi-v2.yaml`.
3. In Copilot Studio, create an agent, add a REST API tool/custom connector, and import the OpenAPI v2 file.
4. Configure the authentication model approved by your tenant team. For production, place Microsoft Entra ID or an approved API gateway in front of the API.
5. Paste `copilot/agent-instructions.md` into the agent instructions, test with non-production data, then publish to the approved channel.
 
## TCS/enterprise readiness notes
This starter is designed for internal hosting and offline processing, but it is not a claim of TCS certification. Before production rollout, complete internal architecture, security, privacy, OSS, vulnerability, DLP, data-retention, audit and Copilot/Power Platform governance reviews. Use TLS, SSO, RBAC, malware scanning, upload limits, secret management, logging without sensitive work notes, and a retention policy. Avoid exposing the API publicly unless approved.
 
## Forecast method and limits
The app groups alerts using severity + assignment group + configuration item + normalized description keywords. It calculates a transparent empirical-Bayes-style recurrence score from current count, cross-week persistence, trend and reopen rate. With only two weekly files, this is a prioritization score rather than a calibrated forecast. For production, retain 8–12+ weeks and back-test precision, recall, calibration and drift; optionally replace the scorer with a time-series or supervised model.
 