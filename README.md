# Gut Health Tracker API

Backend for the Gut Health Tracker mobile app. Task 1 covers the foundation (configuration, async PostgreSQL, authentication) and the daily diary.

## Stack

- FastAPI
- SQLAlchemy 2 async sessions
- PostgreSQL via `asyncpg`
- Alembic migrations
- Pydantic v2
- JWT access tokens and rotating refresh tokens
- Argon2 password hashes
- Firebase Admin for Google and Apple ID tokens

## Layout

```
app/
  api/            HTTP routers and dependencies
  core/           Settings, database session, security
  models/         SQLAlchemy models
  schemas/        Pydantic request and response models
  services/       Business rules and queries
  media/          Local avatar and diary images (`avatars/`, `logs/`)
alembic/          Database migrations
```

Routers stay thin. Services own transactions and ownership checks. Schemas validate input and shape the JSON the mobile client receives. Image bytes never go into PostgreSQL: the `avatar_url` and `photo_url` columns store a path such as `/media/avatars/<id>.jpg`, and API responses expand that to `https://api.yourdomain.com/media/avatars/<id>.jpg` using `PUBLIC_BASE_URL`.

## Prerequisites

- Python 3.11 or newer
- PostgreSQL 14 or newer

Create the database, or start PostgreSQL with Docker:

```powershell
docker run --name guthealth-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=guthealth -p 5432:5432 -d postgres:16
```

## Setup

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY` in `.env` to a random string of at least 32 characters:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`DATABASE_URL` must use the async driver:

```
postgresql+asyncpg://postgres:postgres@localhost:5432/guthealth
```

Apply migrations and start the API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8009
```

Interactive docs (development and staging only): <http://localhost:8009/docs>

## Authentication

`POST /api/v1/auth/register` and `POST /api/v1/auth/login` return an access token, a refresh token, and the user profile. Send the access token as `Authorization: Bearer <access_token>`.

Refresh tokens are stored server-side and rotated on `POST /api/v1/auth/refresh`. Reusing a rotated token revokes every session for that account. `POST /api/v1/auth/logout` revokes the presented refresh token.

Passwords must be 8–128 characters and include a letter and a number. They are stored as Argon2 hashes.

The mobile app signs in with Firebase, then sends the Firebase ID token:

- `POST /api/v1/auth/google` with `{"id_token": "<Firebase ID token>"}` when the token provider is Google
- `POST /api/v1/auth/apple` for Apple
- `POST /api/v1/auth/firebase` for any supported provider (`google.com`, `apple.com`, or email)

The Flutter app and this API must use the same Firebase project. A verified email can link an existing account. A different Firebase user already stored for that email returns 409.

Passwordless email uses a 6-digit code:

1. `POST /api/v1/auth/email/send-code` with `{"email": "user@example.com"}`
2. `POST /api/v1/auth/email/verify-code` with `{"email": "user@example.com", "code": "123456"}`

Codes expire after 10 minutes, a new code is limited to once per minute, and five wrong attempts invalidate the code. When `DEBUG=true`, the response includes `debug_code` so local clients can sign in without SMTP. Production must set `DEBUG=false` and `SMTP_HOST` plus `SMTP_FROM`. The code is never returned in production.

`POST /api/v1/auth/register` and `POST /api/v1/auth/login` remain for email and password. Accounts created by Firebase or an email code have no password.

The profile field `avatar_url` in JSON is the absolute URL. The database column stores the path.

## Onboarding

`PUT /api/v1/onboarding` creates or replaces the profile. `GET /api/v1/onboarding` returns it, or 404 before the first save.

`goals`, `concerns`, and `interests` are lists of unique labels. `target_30_day_goal` is optional text.

The first save sets `users.onboarding_completed` and, when it is still empty, `users.tracking_started_on` to the current UTC date. Both fields are on `GET /api/v1/auth/me`. A completed onboarding means a returning user; an empty one means a new user. A later diary date that is earlier than the start date moves `tracking_started_on` backward and never forward.

## Uploads

`POST /api/v1/uploads?purpose=avatar` or `purpose=log` accepts JPEG, PNG, or WebP up to 5 MB. The file type is taken from the bytes. Files land in `app/media/avatars/` or `app/media/logs/`.

The response is:

```json
{
  "path": "/media/logs/<user-id>_<uuid>.jpg",
  "url": "http://localhost:8009/media/logs/<user-id>_<uuid>.jpg",
  "purpose": "log"
}
```

`purpose=avatar` also writes that path to `users.avatar_url`. A log photo is attached to a food or drink row by sending `path` or `url` as `photo_url`.

## Diary

A user has at most one diary entry per calendar date. The database column is `date`, indexed together with `user_id` and `created_at`.

Each day can include:

- Several bowel logs: time of day, Bristol scale 1–7, pain 0–10, and whether blood was present
- `no_bowel_movement`: when true, the day cannot also contain bowel logs
- Food and drink logs (`kind` is `food` or `drink`)
- Factor chips in `factors`: `stress`, `sleep`, `exercise`, `low_water` (unique, at most four). Free text still goes in `other_factors`
- Optional numbers: `stress_level` 0–10, `sleep_hours`, `exercise_minutes`, and `water_ml`

`GET /api/v1/diary` fills every day in the range. The default is today plus the previous 30 days, and it does not start before `tracking_started_on` when that date falls inside the window. The range cannot exceed 366 days. Each day has `day_status` (`tracked`, `missed`, `open`, `before_start`, `future`) and `stool_status` (`logged`, `none`, `unknown`). `missed` is a past day with no entry. `none` is an explicit “no bowel movement” on a saved day. Those two are not the same. The response also includes `tracking_started_on`. `GET /api/v1/diary/{entry_date}` returns the full day, including today. `PATCH` updates the day; sending `bowel_movements` or `food_drinks` replaces that list.

`POST /api/v1/diary/sync` accepts up to 90 days already saved on the device. A missing date is created; an existing date is replaced. The response returns days whose `updated_at` is on or after `since` (or the last 31 days when `since` is omitted), plus `server_time` for the next cursor. The phone still keeps its own local copy; this endpoint is the server half of that sync.

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | Database connectivity |
| POST | `/api/v1/auth/register` | Create an email account |
| POST | `/api/v1/auth/login` | Start a password session |
| POST | `/api/v1/auth/google` | Sign in with a Google Firebase ID token |
| POST | `/api/v1/auth/apple` | Sign in with an Apple Firebase ID token |
| POST | `/api/v1/auth/firebase` | Sign in with any supported Firebase ID token |
| POST | `/api/v1/auth/email/send-code` | Create a 6-digit email code |
| POST | `/api/v1/auth/email/verify-code` | Sign in with that code |
| POST | `/api/v1/auth/refresh` | Rotate tokens |
| POST | `/api/v1/auth/logout` | Revoke a refresh token |
| GET | `/api/v1/auth/me` | Current profile |
| PATCH | `/api/v1/auth/me` | Update name |
| GET | `/api/v1/onboarding` | Read onboarding |
| PUT | `/api/v1/onboarding` | Save or replace onboarding |
| POST | `/api/v1/uploads` | Upload an avatar or log image |
| GET | `/api/v1/devices` | List the current user's push tokens |
| POST | `/api/v1/devices` | Register or refresh a push token |
| GET | `/api/v1/devices/{device_id}` | Read one push token |
| PATCH | `/api/v1/devices/{device_id}` | Update a push token |
| DELETE | `/api/v1/devices/{device_id}` | Remove a push token |
| POST | `/api/v1/admin/login` | Administrator sign-in |
| GET | `/api/v1/admin/stats` | Dashboard counts |
| GET | `/api/v1/admin/users` | User list |
| GET | `/api/v1/admin/users/{user_id}` | User detail |
| GET | `/api/v1/admin/devices` | All push tokens |
| GET | `/api/v1/admin/devices/{device_id}` | Push token detail |
| GET | `/api/v1/admin/onboarding` | Onboarding list |
| GET | `/api/v1/admin/onboarding/{profile_id}` | Onboarding detail |
| GET | `/api/v1/admin/diary` | Diary list |
| GET | `/api/v1/admin/diary/{entry_id}` | Diary detail |
| GET | `/api/v1/diary` | Calendar view |
| POST | `/api/v1/diary` | Create one day |
| POST | `/api/v1/diary/sync` | Push local days and pull changes |
| GET | `/api/v1/diary/{entry_date}` | Read one day |
| PATCH | `/api/v1/diary/{entry_date}` | Update one day |
| DELETE | `/api/v1/diary/{entry_date}` | Delete one day |

### Create a day

```http
POST /api/v1/diary
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "entry_date": "2026-10-09",
  "no_bowel_movement": false,
  "stress_level": 4,
  "sleep_hours": 7.5,
  "exercise_minutes": 30,
  "water_ml": 1800,
  "other_factors": "Travel day",
  "factors": ["stress", "low_water"],
  "bowel_movements": [
    {
      "occurred_at": "08:30:00",
      "bristol_type": 4,
      "pain_level": 2,
      "blood_present": false
    }
  ],
  "food_drinks": [
    {
      "kind": "food",
      "name": "Oatmeal",
      "consumed_at": "09:00:00",
      "photo_url": "/media/logs/<user-id>_<uuid>.jpg"
    }
  ]
}
```

## Errors

Expected failures use:

```json
{"detail": "Diary entry not found", "code": "not_found"}
```

Common codes: `unauthorized`, `not_found`, `conflict`, `invalid_date_range`, `invalid_bowel_state`, `invalid_media_path`, `file_too_large`, `unsupported_file_type`, `unsupported_provider`, `firebase_not_configured`, `email_not_configured`, `email_failed`, `too_many_requests`, `forbidden`, `admin_not_configured`, `database_unavailable`.

Records that belong to another user are returned as not found.

## Environment

| Variable | Required | Default |
| --- | --- | --- |
| `DATABASE_URL` | yes | — |
| `SECRET_KEY` | yes, min 32 chars | — |
| `ENVIRONMENT` | no | `development` |
| `DEBUG` | no | `false` |
| `PUBLIC_BASE_URL` | no | `http://localhost:8009` |
| `CORS_ORIGINS` | no | `*` (rejected in production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | `14` |
| `MAX_UPLOAD_BYTES` | no | `5242880` |
| `FIREBASE_PROJECT_ID` | for Google and Apple | empty |
| `FIREBASE_PRIVATE_KEY` | for Google and Apple | empty |
| `FIREBASE_CLIENT_EMAIL` | for Google and Apple | empty |
| `SMTP_HOST` | for production email codes | empty |
| `SMTP_FROM` | for production email codes | empty |
| `ADMIN_EMAIL` | for the admin panel | empty |
| `ADMIN_PASSWORD` | for the admin panel | empty |

## Push tokens

`POST /api/v1/devices` stores an FCM token for the signed-in user. Sending the same token again refreshes the platform, name, and last-seen time, and moves the token to the current account if it was registered to someone else.

```json
{
  "token": "<fcm-token>",
  "platform": "ios",
  "device_name": "iPhone 15",
  "app_version": "1.0.0"
}
```

`platform` is `ios`, `android`, or `web`.

## Admin panel

The React admin app lives in the sibling folder `admin-panel`, outside this backend. It signs in with `ADMIN_EMAIL` and `ADMIN_PASSWORD`. The first successful login creates that user with `is_admin = true`.

```powershell
cd ..\admin-panel
npm install
npm run dev
```

The panel runs at <http://localhost:5173> and calls this API at <http://localhost:8009>.

In production, `DEBUG` must be false, `CORS_ORIGINS` must list explicit origins, and OpenAPI docs are disabled.
