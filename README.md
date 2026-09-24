# EcoGuard Uganda — Connected Frontend + Backend

This package is the implementation companion to the EcoGuard Uganda mobile/desktop design deck. It keeps **wildlife detection and human verification** as the primary workflow and also includes wetland and flood reporting.

## Stack
- Frontend: React 19 + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy 2 + Pydantic
- Data: PostgreSQL + PostGIS (Docker Compose)
- Queue/optional background work: Redis + Celery
- Image assistance: optional TorchVision service/checkpoint; suggestions never publish automatically
- Maps: Leaflet dependency and a privacy-safe community map UI
- Auth: HttpOnly session cookie + CSRF token for writes

## Frontend pages
18 community/mobile-oriented pages: welcome, sign-in, home, wildlife upload, identification, sighting, review/submit, success, alerts, alert detail, community, wetland, flood, my reports, progress, messages, settings, help.

10 desktop/staff pages: dashboard, wildlife queue, verification, map, reports, wetlands, flood, alert publishing, analytics, administration.

The supplied visual reference PNGs are included in `frontend/public/design-reference/` and the application uses the same visual language: green/white, rounded panels, wildlife imagery, desktop sidebar/top bar and mobile bottom navigation.

## API communication
The frontend uses `VITE_API_BASE_URL` (default `/api/v1`) and `credentials: include`, so the Vite development proxy sends `/api/*` to FastAPI at `localhost:8000`. Production can set the same variable to an API origin.

Main API groups:
- `/api/v1/auth/*` — registration, login, session, preferences, password
- `/api/v1/reports/*` — create, edit, submit, list, review, assign, close, messages, CSV export
- `/api/v1/evidence/*` — private evidence upload/content
- `/api/v1/advisories/*` — reviewed public advisories
- `/api/v1/workspace/*` — dashboard, map, communities and admin workflows

Interactive API docs are available at `http://localhost:8000/api/docs` when enabled.

## Run with Docker
1. Copy environment values and replace the database password for real deployments.
2. `docker compose up --build`
3. Frontend: `http://localhost:5173`
4. API docs: `http://localhost:8000/api/docs`

## Run locally
Backend:
```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:
```
cd frontend
npm install
npm run dev
```

## Important scope
The UI is fully connected to the API client, but external SMS/WhatsApp/USSD providers and a production-trained wildlife model are intentionally optional integrations. Configure and test them before field use. AI suggestions are not treated as verified findings.
