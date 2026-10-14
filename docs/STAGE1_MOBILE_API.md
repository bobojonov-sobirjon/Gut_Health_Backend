# Gut Health Tracker — Stage 1 Mobile API

Documentation for the mobile frontend. Stage 1 is sign-in, onboarding, the daily diary, photos, and push-token registration. History filters, AI reports, settings, reminders, and account deletion are not in this stage.

## 1. General

| | |
| --- | --- |
| Project | Gut Health Tracker |
| Dev base URL | `http://localhost:8009` |
| Staging base URL | not deployed |
| Prod base URL | `http://152.53.209.29` |
| API prefix | `/api/v1` |
| Framework | FastAPI (Python). This is not Django REST Framework. |
| Authentication | JWT, HS256. Send `Authorization: Bearer <access_token>` |
| JSON content type | `application/json` |
| Upload content type | `multipart/form-data` |
| Swagger | `http://152.53.209.29/docs` |

All paths below are relative to the base URL. Example: prod login is `http://152.53.209.29/api/v1/auth/google`.

Unknown JSON fields are rejected (`extra` fields return 422).

Dates are `YYYY-MM-DD`. Times are `HH:MM:SS`. Timestamps are ISO-8601 with a timezone.

### JWT flow

1. Sign in with Google, Apple, or email code. The response contains `access_token`, `refresh_token`, `expires_in`, and `user`.
2. Send the access token on every protected request: `Authorization: Bearer <access_token>`.
3. The access token lives **30 minutes** (`expires_in` is seconds, `1800`).
4. The refresh token lives **14 days**. `POST /api/v1/auth/refresh` returns a new pair and invalidates the previous refresh token. Replace both tokens in local storage.
5. `POST /api/v1/auth/logout` revokes the refresh token. The access token expires on its own.

There is no `access` / `refresh` field. The names are `access_token` and `refresh_token`.

### New user vs returning user

Read `user` from the auth response, or call `GET /api/v1/auth/me`.

| Field | Type | Meaning |
| --- | --- | --- |
| `onboarding_completed` | boolean | `false`: show onboarding. `true`: returning user, open the app. |
| `tracking_started_on` | string (date) or `null` | First tracking day. Set when onboarding is saved. A later diary date that is earlier moves this backward. It never moves forward. |

### Shared user object

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Maria Ivanova",
  "auth_provider": "google",
  "provider_subject": "firebase-uid",
  "avatar_url": "http://152.53.209.29/media/avatars/....jpg",
  "onboarding_completed": false,
  "tracking_started_on": null,
  "created_at": "2026-10-14T07:00:00Z"
}
```

`auth_provider`: `email` | `google` | `apple`.

`avatar_url` is an absolute URL, or `null`.

### Shared auth response

```json
{
  "access_token": "jwt_access_token",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {}
}
```

`user` is the shared user object. Refresh does **not** include `user`.

### Errors

```json
{
  "detail": "Human readable message",
  "code": "unauthorized"
}
```

Validation errors (422) use FastAPI's `detail` array (`loc`, `msg`, `type`) and may omit `code`.

| HTTP | `code` | When |
| --- | --- | --- |
| 401 | `unauthorized` | Missing/invalid access token, bad login, bad or expired email code |
| 404 | `not_found` | Day, onboarding, or device does not exist for this user |
| 409 | `conflict` | Diary day already exists, or email already registered |
| 400 | `invalid_date_range` | Calendar range is incomplete, reversed, or longer than 366 days |
| 400 | `invalid_bowel_state` | `no_bowel_movement: true` together with bowel logs |
| 400 | `invalid_media_path` | `photo_url` was not uploaded by this account |
| 400 | `empty_file` | Upload body is empty |
| 400 | `email_required` | Firebase token has no email |
| 400 | `unsupported_provider` | Firebase provider is not Google, Apple, or email |
| 413 | `file_too_large` | File is over 5 MB |
| 400 | `unsupported_file_type` | Not JPEG, PNG, or WebP |
| 422 | — | Body/query validation |
| 429 | `too_many_requests` | Email code requested again within 60 seconds |
| 502 | `email_failed` | SMTP send failed |
| 503 | `email_not_configured` | Production email codes need SMTP |
| 503 | `firebase_not_configured` | Firebase Admin is not configured |
| 503 | `database_unavailable` | Database is down |

Another user's row is returned as `not_found`, not 403.

---

## 2. Health

### Health check

- METHOD: `GET`
- URL: `/api/v1/health`
- Auth: no

Response `200`:

```json
{ "status": "ok" }
```

---

## 3. Authentication

Product sign-in is Google, Apple, or email + 6-digit code. Password register/login exist for tools and are documented at the end of this section.

The mobile app gets a **Firebase ID token** from the Google or Apple SDK, then sends that token here. Do not send the Google/Apple identity token directly.

### Google sign-in

- METHOD: `POST`
- URL: `/api/v1/auth/google`
- Auth: no

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id_token` | string | yes | Firebase ID token from Google. Length 20–8192. |

Example request:

```json
{ "id_token": "<firebase-id-token>" }
```

Response `200`: shared auth response. `user.auth_provider` is `google`.

The token must be a Google Firebase sign-in. A token from another provider returns `401`.

### Apple sign-in

- METHOD: `POST`
- URL: `/api/v1/auth/apple`
- Auth: no

Body: same as Google (`id_token`, string, required).

Response `200`: shared auth response. `user.auth_provider` is `apple`.

### Firebase sign-in (any supported provider)

- METHOD: `POST`
- URL: `/api/v1/auth/firebase`
- Auth: no

Body: same `id_token`. Accepts Google, Apple, or Firebase email. Use `/google` or `/apple` when the screen is fixed to one provider.

Response `200`: shared auth response.

### Send email code

- METHOD: `POST`
- URL: `/api/v1/auth/email/send-code`
- Auth: no

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `email` | string | yes | Valid email. Stored lowercased. |

Example request:

```json
{ "email": "user@example.com" }
```

Response `200`:

```json
{
  "detail": "Sign-in code created",
  "expires_in": 600,
  "debug_code": null
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `detail` | string | Status text |
| `expires_in` | integer | Seconds until the code expires. Default 600 (10 minutes). |
| `debug_code` | string or `null` | The 6-digit code. **Only in local debug.** Prod returns `null`. Read the code from email. |

Rules: one new code per email per 60 seconds. Five wrong attempts burn the code.

Prod currently has no SMTP, so this endpoint returns `503` `email_not_configured` until mail is connected. Google and Apple work without it.

### Verify email code

- METHOD: `POST`
- URL: `/api/v1/auth/email/verify-code`
- Auth: no

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `email` | string | yes | Same email the code was sent to |
| `code` | string | yes | Exactly 6 digits, pattern `^\d{6}$` |

Example request:

```json
{
  "email": "user@example.com",
  "code": "048213"
}
```

Response `200`: shared auth response. Creates the account on first success. `user.auth_provider` is `email`.

Wrong or expired code: `401` `unauthorized`. After 5 failures the code is dead and the user must request a new one.

### Refresh

- METHOD: `POST`
- URL: `/api/v1/auth/refresh`
- Auth: no (the refresh token is the credential)

Body:

| Field | Type | Required |
| --- | --- | --- |
| `refresh_token` | string | yes |

Example request:

```json
{ "refresh_token": "<refresh_token>" }
```

Response `200`:

```json
{
  "access_token": "jwt_access_token",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Store the new refresh token. The one you just sent no longer works.

### Logout

- METHOD: `POST`
- URL: `/api/v1/auth/logout`
- Auth: no

Body:

| Field | Type | Required |
| --- | --- | --- |
| `refresh_token` | string | yes |

Example request:

```json
{ "refresh_token": "<refresh_token>" }
```

Response `204` with an empty body.

### Current profile

- METHOD: `GET`
- URL: `/api/v1/auth/me`
- Auth: Bearer access token

Response `200`: shared user object.

Use this on app launch to decide onboarding vs home.

### Update profile

- METHOD: `PATCH`
- URL: `/api/v1/auth/me`
- Auth: Bearer access token

Body (all optional; only send fields that change):

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `full_name` | string or `null` | no | Max 120 characters. Blank becomes `null`. |

Example request:

```json
{ "full_name": "Maria Ivanova" }
```

Response `200`: shared user object.

Avatar is not set here. Upload with `purpose=avatar`.

### Password register (optional, not the product path)

- METHOD: `POST`
- URL: `/api/v1/auth/register`
- Auth: no

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `email` | string | yes | Valid email |
| `password` | string | yes | 8–128 chars, at least one letter and one digit |
| `full_name` | string or `null` | no | Max 120. Default `null`. |

Example request:

```json
{
  "email": "user@example.com",
  "password": "Secret12",
  "full_name": "Maria Ivanova"
}
```

Response `201`: shared auth response.

### Password login (optional, not the product path)

- METHOD: `POST`
- URL: `/api/v1/auth/login`
- Auth: no

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `email` | string | yes | Valid email |
| `password` | string | yes | 1–128 chars |

Example request:

```json
{
  "email": "user@example.com",
  "password": "Secret12"
}
```

Response `200`: shared auth response. Accounts created by Google, Apple, or email code have no password and cannot use this endpoint.

---

## 4. Onboarding

One profile per user. `PUT` creates it or replaces it. The first successful save sets `onboarding_completed` to `true` and, if empty, `tracking_started_on` to today's UTC date.

### Read onboarding

- METHOD: `GET`
- URL: `/api/v1/onboarding`
- Auth: Bearer access token

Response `200`:

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "goals": ["Less bloating"],
  "concerns": ["Irregular stool"],
  "interests": ["Nutrition"],
  "target_30_day_goal": "30 days without stomach pain",
  "created_at": "2026-10-14T07:00:00Z",
  "updated_at": "2026-10-14T07:00:00Z"
}
```

`404` `not_found` before the first save.

### Save onboarding

- METHOD: `PUT`
- URL: `/api/v1/onboarding`
- Auth: Bearer access token

Body:

| Field | Type | Required | Rules | Default |
| --- | --- | --- | --- | --- |
| `goals` | string[] | no | Unique, max 20 items, each max 80 chars | `[]` |
| `concerns` | string[] | no | Same rules | `[]` |
| `interests` | string[] | no | Same rules | `[]` |
| `target_30_day_goal` | string or `null` | no | Max 300 chars. Blank becomes `null`. | `null` |

Example request:

```json
{
  "goals": ["Less bloating"],
  "concerns": ["Irregular stool"],
  "interests": ["Nutrition", "Sleep"],
  "target_30_day_goal": "30 days without stomach pain"
}
```

Response `200`: the onboarding object above.

Screen order in the product: Goal → Concerns → Interests → 30-day goal. Send the whole document on each save.

---

## 5. Diary

One entry per user per calendar date. Bowel logs and food/drink rows belong to that day. The phone keeps its own copy; `POST /api/v1/diary/sync` is the server half.

### Factor chips

`factors` is a list of strings. Allowed values, unique, at most 4:

| Value | Chip |
| --- | --- |
| `stress` | Stress |
| `sleep` | Sleep |
| `exercise` | Exercise |
| `low_water` | Low water |

Free text goes in `other_factors`, not in `factors`.

Optional numbers, separate from the chips:

| Field | Type | Range |
| --- | --- | --- |
| `stress_level` | integer or `null` | 0–10 |
| `sleep_hours` | number or `null` | 0–24, one decimal |
| `exercise_minutes` | integer or `null` | 0–1440 |
| `water_ml` | integer or `null` | 0–20000 |

### Bowel object (write)

| Field | Type | Required | Rules | Default |
| --- | --- | --- | --- | --- |
| `occurred_at` | string (time) | yes | `HH:MM:SS` | — |
| `bristol_type` | integer | yes | 1 (hard) through 7 (liquid) | — |
| `pain_level` | integer | yes | 0–10 | — |
| `blood_present` | boolean | no | | `false` |

`no_bowel_movement: true` cannot be sent together with a non-empty `bowel_movements` list (`400` `invalid_bowel_state`). Several bowel logs per day are allowed (max 20).

### Food / drink object (write)

| Field | Type | Required | Rules | Default |
| --- | --- | --- | --- | --- |
| `kind` | string | yes | `food` or `drink` | — |
| `name` | string | yes | 1–200 chars | — |
| `consumed_at` | string (time) or `null` | no | `HH:MM:SS` | `null` |
| `notes` | string or `null` | no | Max 2000 | `null` |
| `photo_url` | string or `null` | no | Path or URL returned by upload, max 500 | `null` |

Max 50 food/drink rows per day.

### Day object (response)

```json
{
  "id": "uuid",
  "entry_date": "2026-10-13",
  "no_bowel_movement": false,
  "stress_level": 2,
  "sleep_hours": 8.0,
  "exercise_minutes": 40,
  "water_ml": 2100,
  "other_factors": "Evening walk",
  "factors": ["sleep", "exercise"],
  "bowel_movements": [
    {
      "id": "uuid",
      "occurred_at": "07:45:00",
      "bristol_type": 3,
      "pain_level": 1,
      "blood_present": false,
      "created_at": "2026-10-13T08:00:00Z"
    }
  ],
  "food_drinks": [
    {
      "id": "uuid",
      "kind": "drink",
      "name": "Kefir",
      "consumed_at": "19:30:00",
      "notes": "A glass before bed",
      "photo_url": null,
      "created_at": "2026-10-13T19:40:00Z"
    }
  ],
  "created_at": "2026-10-13T08:00:00Z",
  "updated_at": "2026-10-13T19:40:00Z"
}
```

`photo_url` in responses is an absolute URL.

### Calendar

- METHOD: `GET`
- URL: `/api/v1/diary`
- Auth: Bearer access token

Query:

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `start_date` | string (date) | both or neither | today minus 30 days, but not before `tracking_started_on` when that date falls inside the window |
| `end_date` | string (date) | both or neither | today (UTC) |

Max span is 366 days. Sending only one of the two dates returns `400` `invalid_date_range`.

Example: `GET /api/v1/diary?start_date=2026-10-01&end_date=2026-10-14`

Response `200`:

```json
{
  "tracking_started_on": "2026-10-12",
  "total": 3,
  "items": [
    {
      "entry_date": "2026-10-14",
      "day_status": "open",
      "stool_status": "unknown",
      "has_entry": false,
      "no_bowel_movement": false,
      "bowel_movement_count": 0,
      "food_drink_count": 0,
      "created_at": null
    }
  ]
}
```

Every date in the range is returned, including days with no row. Newest first.

`day_status`:

| Value | Meaning |
| --- | --- |
| `tracked` | A diary row exists |
| `missed` | A past day, on or after the start date, with no row |
| `open` | Today, no row yet. This is not missed. |
| `before_start` | Before `tracking_started_on` |
| `future` | After today |

`stool_status`:

| Value | Meaning |
| --- | --- |
| `logged` | The day has at least one bowel log |
| `none` | The user explicitly set “no bowel movement” |
| `unknown` | No stool answer, or the day has no row |

`missed` and `none` are different. `missed` means the user did not open that day. `none` means they saved the day and said there was no bowel movement.

`bowel_movement_count` and `food_drink_count` are counts, not ids.

### Create a day

- METHOD: `POST`
- URL: `/api/v1/diary`
- Auth: Bearer access token

Body:

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `entry_date` | string (date) | yes | — |
| `no_bowel_movement` | boolean | no | `false` |
| `stress_level` | integer or `null` | no | `null` |
| `sleep_hours` | number or `null` | no | `null` |
| `exercise_minutes` | integer or `null` | no | `null` |
| `water_ml` | integer or `null` | no | `null` |
| `other_factors` | string or `null` | no | `null` |
| `factors` | string[] | no | `[]` |
| `bowel_movements` | bowel[] | no | `[]` |
| `food_drinks` | food[] | no | `[]` |

Example request:

```json
{
  "entry_date": "2026-10-13",
  "no_bowel_movement": false,
  "stress_level": 2,
  "sleep_hours": 8.0,
  "exercise_minutes": 40,
  "water_ml": 2100,
  "other_factors": "Evening walk",
  "factors": ["sleep", "exercise"],
  "bowel_movements": [
    {
      "occurred_at": "07:45:00",
      "bristol_type": 3,
      "pain_level": 1,
      "blood_present": false
    }
  ],
  "food_drinks": [
    {
      "kind": "drink",
      "name": "Kefir",
      "consumed_at": "19:30:00",
      "notes": "A glass before bed",
      "photo_url": "/media/logs/<user-id>_<uuid>.jpg"
    }
  ]
}
```

Response `201`: day object.

A second create for the same date returns `409` `conflict`. Update that day with `PATCH` instead.

“No bowel movement today”:

```json
{
  "entry_date": "2026-10-13",
  "no_bowel_movement": true,
  "bowel_movements": [],
  "factors": ["stress"]
}
```

### Read one day (Today)

- METHOD: `GET`
- URL: `/api/v1/diary/{entry_date}`
- Auth: Bearer access token

Path:

| Field | Type | Required |
| --- | --- | --- |
| `entry_date` | string (date) | yes |

Example: `GET /api/v1/diary/2026-10-13`

Response `200`: day object. `404` `not_found` if that date was never saved.

### Update one day

- METHOD: `PATCH`
- URL: `/api/v1/diary/{entry_date}`
- Auth: Bearer access token

Path: `entry_date` (date, required).

Body: same fields as create, every field optional. Omitted fields stay as they are. Send `null` to clear a nullable field.

| Field | Type | Notes |
| --- | --- | --- |
| `entry_date` | string (date) or omitted | Moves the day. Must not collide with another saved day. |
| `no_bowel_movement` | boolean or omitted | |
| `stress_level` | integer or `null` | |
| `sleep_hours` | number or `null` | |
| `exercise_minutes` | integer or `null` | |
| `water_ml` | integer or `null` | |
| `other_factors` | string or `null` | |
| `factors` | string[] or omitted | Replaces the chip list |
| `bowel_movements` | bowel[] or omitted | **Replaces** the whole bowel list. Omit to leave it. |
| `food_drinks` | food[] or omitted | **Replaces** the whole food/drink list. Omit to leave it. |

Example request:

```json
{
  "factors": ["stress", "low_water"],
  "water_ml": 1200
}
```

Response `200`: day object.

### Delete one day

- METHOD: `DELETE`
- URL: `/api/v1/diary/{entry_date}`
- Auth: Bearer access token

Response `204` with an empty body. `404` if the day does not exist.

### Sync local days

The phone keeps the offline queue. This call uploads saved days, then returns days changed on the server.

- METHOD: `POST`
- URL: `/api/v1/diary/sync`
- Auth: Bearer access token

Body:

| Field | Type | Required | Rules | Default |
| --- | --- | --- | --- | --- |
| `since` | string (datetime) or `null` | no | Must include a timezone offset, for example `2026-10-13T00:00:00Z` | `null` (server uses the last 31 days) |
| `entries` | day-create[] | no | Max 90. Same shape as create. Duplicate dates in one request: the last one wins. | `[]` |

Example request:

```json
{
  "since": "2026-10-01T00:00:00Z",
  "entries": [
    {
      "entry_date": "2026-10-13",
      "no_bowel_movement": false,
      "factors": ["sleep"],
      "bowel_movements": [],
      "food_drinks": []
    }
  ]
}
```

A missing date is created. An existing date is replaced with this payload (bowel and food lists included).

Response `200`:

```json
{
  "server_time": "2026-10-14T08:00:00Z",
  "entries": []
}
```

`entries` are full day objects whose `updated_at` is on or after `since`, max 90. Save `server_time` and send it as `since` on the next sync.

---

## 6. Uploads

- METHOD: `POST`
- URL: `/api/v1/uploads?purpose=avatar` or `/api/v1/uploads?purpose=log`
- Auth: Bearer access token
- Content-Type: `multipart/form-data`

Query:

| Field | Type | Required | Values |
| --- | --- | --- | --- |
| `purpose` | string | yes | `avatar` or `log` |

Form:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `file` | file | yes | JPEG, PNG, or WebP. Type is taken from the bytes, not the filename. Max 5 MB (5242880 bytes). |

`purpose=avatar` also writes the path onto the user's `avatar_url`.

`purpose=log` only stores the file. Attach it by sending the returned `path` or `url` as `photo_url` on a food/drink row.

Response `201`:

```json
{
  "path": "/media/logs/<user-id>_<uuid>.jpg",
  "url": "http://152.53.209.29/media/logs/<user-id>_<uuid>.jpg",
  "purpose": "log"
}
```

Show `url` in the UI. Send `path` or `url` back as `photo_url`.

---

## 7. Push device tokens

One row per token. Sending the same token again updates platform, name, app version, and last-seen time, and moves the token onto the current account if it belonged to someone else.

### Device object

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "token": "<fcm-token>",
  "platform": "ios",
  "device_name": "iPhone 15",
  "app_version": "1.0.0",
  "is_active": true,
  "last_seen_at": "2026-10-14T08:00:00Z",
  "created_at": "2026-10-14T08:00:00Z",
  "updated_at": "2026-10-14T08:00:00Z"
}
```

`platform`: `ios` | `android` | `web`.

### Register or refresh a token

- METHOD: `POST`
- URL: `/api/v1/devices`
- Auth: Bearer access token

Body:

| Field | Type | Required | Rules | Default |
| --- | --- | --- | --- | --- |
| `token` | string | yes | 10–512 chars, not blank | — |
| `platform` | string | yes | `ios`, `android`, or `web` | — |
| `device_name` | string or `null` | no | Max 120 | `null` |
| `app_version` | string or `null` | no | Max 40 | `null` |

Example request:

```json
{
  "token": "<fcm-token>",
  "platform": "ios",
  "device_name": "iPhone 15",
  "app_version": "1.0.0"
}
```

Response `201`: device object.

### List my tokens

- METHOD: `GET`
- URL: `/api/v1/devices`
- Auth: Bearer access token

Response `200`: array of device objects. Empty array if none.

### Read one token

- METHOD: `GET`
- URL: `/api/v1/devices/{device_id}`
- Auth: Bearer access token

Path: `device_id` (uuid, required).

Response `200`: device object. `404` if it is not this user's token.

### Update a token

- METHOD: `PATCH`
- URL: `/api/v1/devices/{device_id}`
- Auth: Bearer access token

Body (all optional):

| Field | Type | Rules |
| --- | --- | --- |
| `platform` | string | `ios`, `android`, or `web` |
| `device_name` | string or `null` | Max 120 |
| `app_version` | string or `null` | Max 40 |
| `is_active` | boolean | |

Example request:

```json
{ "is_active": false }
```

Response `200`: device object.

### Delete a token

- METHOD: `DELETE`
- URL: `/api/v1/devices/{device_id}`
- Auth: Bearer access token

Response `204` with an empty body.

---

## 8. What the app should do

1. Sign in with Google, Apple, or email code.
2. If `onboarding_completed` is `false`, show Goal → Concerns → Interests → 30-day goal, then `PUT /api/v1/onboarding`.
3. Today is `GET /api/v1/diary/{today}`. A `404` means the day is not saved yet. Create it with `POST /api/v1/diary`.
4. The calendar is `GET /api/v1/diary`. Paint days from `day_status` and stool from `stool_status`. Do not treat `missed` as “no bowel movement”.
5. Edit a saved day with `PATCH`. Delete with `DELETE`.
6. Keep unsynced edits on the phone. Flush them with `POST /api/v1/diary/sync`.
7. After a photo pick, `POST /api/v1/uploads?purpose=log`, then put `path` into `photo_url`.
8. After notification permission, `POST /api/v1/devices` with the FCM token.

The admin panel (`http://152.53.209.29/`) is a separate web app. Its `/api/v1/admin/...` routes are not part of the mobile stage 1 contract.
