# Architecture

## Boundaries

- `frontend`: React/TypeScript single-page application. Rendering, local interaction state, accessibility, and optimistic feedback.
- `backend`: FastAPI application. Curriculum delivery, authoritative answer validation, session scoring, unlock rules, streaks, and progress.
- `db`: PostgreSQL. Curriculum snapshots, learner state, attempts, sessions, mastery, and achievements.

Curriculum ships as versioned Python seed data for reviewability. The API exposes a stable JSON contract and never sends correct-answer keys in lesson payloads. A single local learner is created lazily from the browser-generated UUID.

## Data model

- learners: identity, XP, streak, last-active date, daily goal.
- lesson_progress: state, best score, attempts, completion and mastery.
- lesson_sessions: resumable run, current position, hearts, score, status.
- exercise_attempts: supplied answer, correctness, attempt number, feedback.

Curriculum definitions are currently code-owned and versioned. This avoids premature CMS complexity while preserving an obvious migration to database-authored content later.

## API

- `GET /health`
- `GET /api/course?learner_id=...`
- `GET /api/dashboard?learner_id=...`
- `POST /api/lessons/{slug}/sessions`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/answer`
- `GET /api/progress?learner_id=...`

The answer endpoint is idempotent per session position: repeated submissions after a correct answer return the accepted result without awarding XP twice.
