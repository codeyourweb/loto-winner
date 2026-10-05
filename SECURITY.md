# 🔐 Security — Loto Winner

This document describes **the hardening measures applied** to the application and
**the security tests carried out** to validate them. It is separate from
[`README.md`](README.md), which covers the business behaviour and the
functional and technical tests.

> **Scope**: Flask API (`backend/`) and its WSGI server. The React interface
> is served as static content; it holds no secret.
>
> **Frameworks**: [OWASP Top 10 (2021)](https://owasp.org/Top10/) and
> [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/).

---

## 1. Threat model

| Asset | Main threat | Countermeasure |
| --- | --- | --- |
| Flask server | Denial of service (expensive replay in a loop) | Rate limiting, input bounds |
| SQLite database | SQL injection via query parameters | 100% parameterised queries, strict parsing |
| FDJ import | Malicious archive / corrupted file | HTTPS download, defensive parsing, validation bounds |
| Configuration | Leak of `SECRET_KEY`, open CORS | Mandatory environment variables, allowlist |
| HTTP responses | Leak of versions / technical traces | Hardened headers, generic errors, masked banner |
| Client browser | XSS / clickjacking | Restrictive CSP, `X-Frame-Options: DENY` |

**Assumptions**: no authentication (public read-only API + stateless
computation), no personal data stored. Only outbound call: downloading the
official FDJ archives, only at startup and via `POST /api/admin/sync`
(rate-limited).

---

## 2. Hardening measures

### 2.1 Security headers

Applied to **all** responses (success and errors alike) by the
`after_request` hook — see [`backend/app/security.py`](backend/app/security.py).

| Header | Value | Protects against |
| --- | --- | --- |
| `Content-Security-Policy` | `default-src 'self'; …; frame-ancestors 'none'; object-src 'none'; base-uri 'self'` | XSS, clickjacking, base injection |
| `X-Content-Type-Options` | `nosniff` | MIME type sniffing |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `Referrer-Policy` | `no-referrer` | URL leak via the referer |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(), payment=()` | Access to browser APIs |
| `Cross-Origin-Opener-Policy` | `same-origin` | Cross-origin context leak |
| `Cross-Origin-Resource-Policy` | `same-origin` | Cross-origin resource loading |
| `X-Permitted-Cross-Domain-Policies` | `none` | Legacy Flash/PDF policies |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS downgrade — **production only** |
| `Server` | `Loto-Winner` | Version disclosure (Werkzeug masked) |

### 2.2 Strict input validation

See [`backend/app/loto_logic.py`](backend/app/loto_logic.py) and
[`backend/app/security.py`](backend/app/security.py).

- **Types**: only "plain" integers are accepted. Strings, floats and
  booleans (`True` being an `int` in Python, it is explicitly excluded) are
  rejected with HTTP 400.
- **Query parameters**: validated by the regex `^[0-9]{1,9}$` then bounded
  (`limit` ≤ 500, `offset` ≥ 0). Any malformed value → 400, never 500.
- **List size**: bounded to 64 elements (a grid contains 5).
- **Duplicates**: rejected.
- **Request body**: `MAX_CONTENT_LENGTH` = 64 KiB → HTTP 413.

### 2.3 Database

- **100% parameterised SQL queries** (`?`): no string concatenation.
- Connection opened with `timeout=5.0` to prevent a blocked query from
  stalling the server.
- `PRAGMA foreign_keys = ON`.

### 2.4 Configuration

See [`backend/app/config.py`](backend/app/config.py).

| Setting | Development | Production |
| --- | --- | --- |
| `DEBUG` | `False` | `False` |
| `SECRET_KEY` | env or `None` | **mandatory** (no weak default) |
| CORS | `localhost:5173` | **allowlist** provided, never `*` |
| Cookies | `HttpOnly`, `SameSite=Lax` | + `Secure` |
| HSTS | disabled | enabled |
| Rate limit | 30/min on simulation | same, Redis store recommended |

The production safeguard is in
[`backend/wsgi.py`](backend/wsgi.py): startup **fails** if
`LOTO_SECRET_KEY` or `LOTO_CORS_ORIGINS` are missing.

### 2.5 Rate limiting

See [`backend/app/extensions.py`](backend/app/extensions.py) and
[`backend/app/routes.py`](backend/app/routes.py).

| Scope | Limit |
| --- | --- |
| Global (`RATELIMIT_DEFAULT`) | 300 / minute / IP |
| `POST /api/simulate` (the most expensive) | 30 / minute / IP |
| `POST /api/simulate/pdf` (PDF generation) | 20 / minute / IP |
| `POST /api/admin/sync` (network + write) | 5 / minute / IP |
| Exceeded | HTTP 429 + `Retry-After` |

In multi-worker setups, point `RATELIMIT_STORAGE_URI` at Redis so that the
counter is shared.

### 2.6 PDF generation

The PDF export (`backend/app/pdf_report.py`) is generated server-side with
ReportLab: no browser engine is exposed. Measures applied:

- content **never cached** (`Cache-Control: no-store`);
- file name **sanitised** (numbers and chance only), with no control
  character able to inject a header;
- MIME type forced to `application/pdf` (no HTML/XSS confusion);
- input validation identical to `/api/simulate`;
- dedicated rate limit.

### 2.6 Error handling

No technical trace is returned to the client. The handlers cover
400, 404, 405, 413, 429 and 500 with generic messages. The business
`ValidationError` is translated into an explicit 400 via a blueprint
`errorhandler`.

---

## 3. OWASP Top 10 (2021) coverage

| Category | Status | Measure applied | Test class |
| --- | --- | --- | --- |
| **A01** Broken Access Control | ✅ | No privileged access exposed; generic errors | `TestSecurityHeaders` |
| **A02** Cryptographic Failures | ✅ | Secret mandatory in prod; hardened cookies | `TestSessionHardening` |
| **A03** Injection | ✅ | Parameterised SQL, type validation, regex parsing | `TestInjectionResistance` |
| **A04** Insecure Design | ✅ | Input bounds, rate limiting, DB timeout | `TestResourceConsumption` |
| **A05** Security Misconfiguration | ✅ | CORS allowlist, `DEBUG=False`, headers | `TestMisconfiguration` |
| **A06** Vulnerable Components | ✅ | Pinned versions, updates tracked | — (process) |
| **A07** Auth Failures | ✅ | No auth surface, neutral messages | `TestAuthenticationSurface` |
| **A08** Integrity Failures | ✅ | Typed inputs, no untrusted deserialisation | `TestInjectionResistance` |
| **A09** Logging Failures | ✅ | `/api/health` for monitoring, observable 429s | `TestObservability` |
| **A10** SSRF | ✅ | No outbound request from the API | — (architectural) |

> The PDF export is covered by the `TestPdfExportSecurity` classes
> (injection, cache, MIME type, file name header) and
> `TestResourceConsumption` (dedicated rate limit).

### OWASP API Security Top 10 (2023)

| Reference | Status | Measure |
| --- | --- | --- |
| **API1** BOLA | N/A | No user resource, no object identifier |
| **API2** Broken Authentication | N/A | No authentication |
| **API3** Broken Object Property Level Authorization | ✅ | Fixed response fields, no arbitrary write |
| **API4** Unrestricted Resource Consumption | ✅ | `MAX_CONTENT_LENGTH`, rate limiting, list bounds |
| **API5** Broken Function Level Authorization | N/A | No administrative function |
| **API6** Unrestricted Access to Sensitive Business Flows | ✅ | `/api/simulate` rate-limited |
| **API7** SSRF | ✅ | No outbound request |
| **API8** Security Misconfiguration | ✅ | See A05 |
| **API9** Improper Inventory Management | ✅ | Explicit routes, no obsolete version |
| **API10** Unsafe Consumption of APIs | N/A | No third-party API consumed |

---

## 4. Detailed inventory of the security tests

File: [`backend/tests/security/test_owasp.py`](backend/tests/security/test_owasp.py)

### 4.1 `TestSecurityHeaders` — headers and HTTP hardening

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_headers_present_on_api_responses` | 5 hardened headers on `/api/health` | All present and exact |
| `test_headers_present_on_error_responses` | The same on a 404 response | All present and exact |
| `test_csp_forbids_framing_and_inline_scripts` | CSP content | `frame-ancestors 'none'`, `object-src 'none'`, `default-src 'self'` |
| `test_server_banner_is_masked` | `Server` header | Neither `Werkzeug` nor `/` |
| `test_hsts_present_only_in_production` | HSTS depending on the profile | Absent in dev, `max-age=` in prod |

### 4.2 `TestSessionHardening` — cookies and secrets

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_session_cookie_is_httponly_and_samesite` | Session cookie flags | `HttpOnly=True`, `SameSite ∈ {Lax, Strict}` |
| `test_production_forces_secure_cookies` | Secure cookie in prod | `SESSION_COOKIE_SECURE=True` |
| `test_production_does_not_ship_a_default_secret` | Absence of a fallback key | `SECRET_KEY` empty if not supplied |

### 4.3 `TestInjectionResistance` — SQL, JSON and type injection

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_sql_injection_in_query_param_is_rejected` | `limit=1; DROP TABLE draws;--` | HTTP 400 JSON |
| `test_sql_injection_in_query_param_leaves_db_intact` | Integrity after the attempt | `/api/draws` and `/api/health` OK |
| `test_malformed_limit_values_are_rejected` *(parameterised)* | `5 OR 1=1`, `../../etc/passwd`, `0x10`, `1e3`, `-1` | HTTP 400 for each |
| `test_numbers_with_strings_are_rejected` | `["1","2",…]` | HTTP 400 |
| `test_numbers_with_floats_are_rejected` | `[1.5, 2.5, …]` | HTTP 400 |
| `test_numbers_with_booleans_are_rejected` | `[true, false, …]` | HTTP 400 |
| `test_sql_keyword_in_string_field_is_not_executed` | `"'; DROP TABLE simulations;--"` | HTTP 400, table intact |

### 4.4 `TestResourceConsumption` — resource consumption

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_max_content_length_is_configured` | Body cap | ≤ 1 MiB |
| `test_oversized_numbers_list_is_rejected` | List of 499 numbers | HTTP 400 |
| `test_limit_upper_bound_is_enforced` | Pagination bounds | 500 → 200; 501 → 400 |
| `test_negative_offset_is_rejected` | `offset=-1` | HTTP 400 |
| `test_rate_limit_is_registered_on_simulate` | Limit active by default | `RATELIMIT_ENABLED`, "minute" limit |
| `test_oversized_body_is_rejected_with_413` | Body of 128 KiB | HTTP 413 |

### 4.5 `TestMisconfiguration` — misconfiguration

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_debug_is_disabled_by_default` | Debug mode | `False` |
| `test_cors_uses_an_allowlist_not_wildcard` | CORS list | No `*` |
| `test_disallowed_origin_gets_no_cors_grant` | Origin `evil.example` | No `Access-Control-Allow-Origin` granted |
| `test_allowed_origin_is_granted` | Legitimate origin | CORS header returned |
| `test_error_does_not_leak_stack_trace` | Invalid JSON | 400 without `Traceback` or `File "` |

### 4.6 `TestAuthenticationSurface` — authentication surface

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_no_endpoint_exposes_credentials` | Root page | No `password`/`secret` |
| `test_error_messages_do_not_reveal_internal_details` | `limit=abc` | Body `{"error": …}` without `sqlite` |

### 4.7 `TestObservability` — monitoring and logging

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_health_endpoint_available_for_monitoring` | `/api/health` | `status="ok"` + draw counter |
| `test_rate_limit_returns_429_when_exceeded` | 2nd call beyond the limit | HTTP 429 (and `Retry-After`/JSON) |

### 4.8 `TestPdfExportSecurity` — PDF export

| Test | What is checked | Expected result |
| --- | --- | --- |
| `test_pdf_export_is_rate_limited` | Limit dedicated to the export | `RATELIMIT_PDF` configured |
| `test_pdf_endpoint_rejects_injection_attempts` | SQL payload in the grid | HTTP 400, database intact |
| `test_pdf_response_is_not_cacheable` | Cache header | `Cache-Control: no-store` |
| `test_pdf_response_has_security_headers` | Hardened headers on the PDF | `nosniff`, `DENY` |
| `test_pdf_content_type_cannot_be_confused` | MIME type | `application/pdf`, no `html` |
| `test_pdf_filename_cannot_inject_headers` | File name | No `\r` or `\n` |

---

## 5. Running the security tests

```powershell
cd backend

# Security only
.\.venv\Scripts\python.exe -m pytest tests/security -v

# With details of the parameterised cases
.\.venv\Scripts\python.exe -m pytest tests/security -v -ra

# The whole suite (functional + technical + security)
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux / macOS:

```bash
cd backend
.venv/bin/python -m pytest tests/security -v
```

The security fixtures are defined in
[`backend/tests/conftest.py`](backend/tests/conftest.py):

| Fixture | Role |
| --- | --- |
| `app` | Application in `TestConfig` configuration, isolated temporary database |
| `client` | HTTP client attached to `app` |
| `production_app` | Application in `ProductionConfig` (HSTS, `Secure` cookies, strict CORS) |
| `valid_payload` | Reusable valid JSON body |

---

## 6. Reporting a vulnerability

If you discover a flaw, **do not open a public issue**. Contact the
repository maintainer privately (channel indicated in the project profile) with:

1. the description and estimated impact;
2. the reproduction steps (request, payload, context);
3. the affected version.

**Commitment**: acknowledgement within 72 h, assessment and fix as soon as
possible, credit to the reporter if desired.

---

## 7. Pre-launch checklist

- [ ] `LOTO_SECRET_KEY` generated randomly (≥ 32 characters) and **outside the repository**.
- [ ] `LOTO_CORS_ORIGINS` limited to the real domain(s), never `*`.
- [ ] **TLS** reverse proxy in front of the API (nginx, Caddy, IIS); HSTS active.
- [ ] `RATELIMIT_STORAGE_URI` pointed at **Redis** (multi-worker shared counter).
- [ ] `LOTO_DB_PATH` placed **outside** the directory served by the proxy.
- [ ] `DEBUG` disabled; production WSGI server (waitress/gunicorn), not `run.py`.
- [ ] Security headers verified on the real instance (e.g. `curl -I`).
- [ ] Monitoring `/api/health` and alerting on 5xx errors / spikes of 429.
- [ ] Database backups and a dependency update policy in place.

---

## 8. Known limitations

| Point | Detail |
| --- | --- |
| No WAF | Hardening is at the application level; a WAF/CDN is still recommended upstream. |
| In-memory storage | Without Redis, the rate counter is **per worker** (can be bypassed in multi-process). |
| Public API | No authentication: suitable for demonstration use, not for private data. |
| Simulated data | The draw history is generated; no real FDJ data is redistributed. |
| Static tests | No automated SAST/DAST analysis is included (to be added in CI). |

---

*Last updated: 2026-10-05 — security suite: 40 test cases.*
