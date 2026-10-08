# CAT Intelligence

Nairobi urban flood catastrophe model for the Kenya Re AI4Insurance Hackathon 2026 (Team A).

The application reads a synthetic building portfolio, runs a deterministic loss engine, and serves the results through a Django API to a React interface. Figures on screen are copied from the engine.

```
Hazard → Exposure → Vulnerability → Financial loss → Portfolio risk → Review
```

## What the numbers mean

The 600 buildings and their values were supplied by the hackathon organizers. They do not describe real properties.

The hazard layers are a susceptibility proxy. They are not flood depths, probabilities, or modelled flood events. Return-period labels (10, 25, 50, 100, and 250 years) are provisional display labels from decision D-004. Damage parameter H is an assumption with no Nairobi calibration, and one vulnerability curve shape is used for every housing class.

## Layout

```
backend/          Django API (portfolio, buildings, loss curve, hotspots)
frontend/         React application (Vite)
loss_engine/      Validation, configuration, vulnerability, building loss, aggregation
data/             Organizer source data, unchanged
docs/             Frozen specification, decision record, and reference notes
tests/            Loss-engine tests
PROVENANCE.md     Hashes and facts for the source files
```

Generated files belong in `outputs/`, which Git ignores.

## Requirements

- Python 3.13 or newer
- Node.js 20 or newer

## Setup

From the repository root.

**Windows**

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
cd frontend
npm install
```

**macOS or Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm install
```

`backend/requirements.txt` pins Django, NumPy, and pandas, which is everything the API needs. `requirements-lock.txt` pins the versions the test suite passed with, including pytest.

## Run

Use two terminals. Start the API first, then the interface.

**API** — http://127.0.0.1:8000

```powershell
.\.venv\Scripts\python backend\manage.py migrate
.\.venv\Scripts\python backend\manage.py runserver 127.0.0.1:8000
```

**Interface** — http://127.0.0.1:5173

```powershell
cd frontend
npm run dev
```

On macOS or Linux, call `.venv/bin/python` instead of `.\.venv\Scripts\python`.

The Vite dev server proxies `/api` to the Django process, so the browser only needs the address above. Open http://127.0.0.1:5173 after both processes are up. The first load asks the API for the full portfolio.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/portfolio/` | Portfolio, buildings, tier and class summaries, hotspots |
| GET | `/api/buildings/` | Building list |
| GET | `/api/buildings/<loc_id>/` | One building |
| GET | `/api/loss-curve/?assumption=reference` | Loss by assumed return period |
| GET | `/api/hotspots/` | Named locations for the map |

`assumption` is one of `reference`, `low`, `high`, or `reference_rcc80`.

Accounts are stored in SQLite (`backend/db.sqlite3`) and authenticated with a Django session. Passwords are hashed. The React app is served from `http://127.0.0.1:5173`; that origin is allowed for CSRF and credentialed requests. Before a state-changing call, `GET /api/auth/csrf/` issues the token to send as `X-CSRFToken`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/auth/csrf/` | Issue the CSRF cookie and token |
| POST | `/api/auth/register/` | Create an account (`name`, `email`, `password`) |
| POST | `/api/auth/login/` | Start a session. Email is the identifier |
| POST | `/api/auth/logout/` | End the current session |
| GET | `/api/auth/me/` | Return the signed-in user, or 401 |

## Tests

From the repository root, with the virtual environment active:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m pytest
```

GitHub Actions runs the same install and `pytest` on every push and pull request.

## Modelling notes

- The hazard score is a relative susceptibility score, not a flood depth (D-002).
- The score is placed on the published JRC Africa residential curve through one scale parameter, H, run at 2, 4, and 6 (D-005).
- Housing classes differ only through structure-only damage ceilings. Those ceilings are team assumptions (D-005).
- `tiv_kes` is used exactly as supplied (D-001).
- Each configuration has a `parameter_set_id`: the SHA-256 of a fixed JSON text of every parameter and source tag.

Contents, business interruption, deductibles, limits, and reinsurance are out of scope. The engine does not redraw the hazard rasters; it uses the scores already attached to the exposure file.

The frozen specification and decision record live in `docs/specifications/` and `docs/decisions/`. Do not edit those documents or the files in `data/`.
