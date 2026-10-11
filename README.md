# Clinic Discovery Platform

Public-facing responsive website planned for Kolkata, West Bengal. The clinic data provider remains undecided. Appointment booking is deferred. Medicine scope includes pharmacy presence and specific medicine stock, but stock display is blocked until a reliable data source/update process is selected.

## Documentation
Start with `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/OPEN_QUESTIONS.md`, and `docs/IMPLEMENTATION_ROADMAP.md`.

## Current implementation step
A minimal FastAPI health endpoint and pytest test are included in `backend/`. This is a scaffold, not a complete application. No database, frontend, real clinic data, external provider, login, or booking is included yet.

## Run backend locally
From the repository root, use Python 3.11+ (or a compatible supported Python version):

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`. In a second terminal with the same environment activated, run `python -m pytest`.

## Run frontend locally

The frontend is plain HTML, CSS and JavaScript; it does not use `npm start`.
Start a static web server from the repository root in a second terminal:

```bash
python -m http.server 5500 --directory frontend
```

Then open `http://127.0.0.1:5500`. Keep the FastAPI server running on port
`8000`, because the frontend checks `GET http://127.0.0.1:8000/health` before
enabling the demo search. Opening `frontend/index.html` directly with a
`file://` URL is not the supported setup.

Do not use invented clinic data in a public release. Confirm provider terms, privacy/security, data verification, and operational responsibilities before launch.
