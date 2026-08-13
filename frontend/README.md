# RegTech Platform — Case Dashboard

Investigator-facing frontend: browse the case queue, drill into what
triggered a case (a sanctions screening or transaction alert), resolve it
with an outcome, leave notes, and file a regulatory report once confirmed.
Vite + React + TypeScript, no UI framework or state-management library --
see `../README.md`'s "Frontend" section for the design rationale.

This is deliberately not a CRUD panel for every backend module: customers,
identity checks, sanctions screenings, and transactions are typically
created by an integrating system, not typed into a form, so those stay
API-only. The one workflow that's genuinely a human's day-to-day job is
case investigation, and that's what this covers.

## Setup

```bash
npm install
cp .env.example .env   # only needed if the backend isn't on localhost:8000
```

## Run

The backend must be running separately (see the root `README.md`) with
`cors_allowed_origins` covering this dev server's origin (defaults to
`http://localhost:5173`, which matches Vite's default port -- no config
needed for local dev).

```bash
npm run dev
```

Open the printed `localhost:5173` URL. You'll land on a connect screen --
paste an API key created via:

```bash
python -m app.cli create-api-key <tenant-slug> <label>
```

## Build

```bash
npm run build
```

Type-checks (`tsc -b`) and produces a production build in `dist/`.
