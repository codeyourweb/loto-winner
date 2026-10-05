"""Security tests aligned with the OWASP Top 10 (2021) and the OWASP API Top 10.

Each test class targets a specific category so as to limit any risk of
compromise of the application or the server once it goes live.
"""

from __future__ import annotations

import json

import pytest

# ===========================================================================
# A01:2021 — Broken Access Control / A05 — Security Misconfiguration
# ===========================================================================


class TestSecurityHeaders:
    """The hardening headers must be present on every response."""

    REQUIRED = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
    }

    def test_headers_present_on_api_responses(self, client):
        response = client.get("/api/health")
        for header, expected in self.REQUIRED.items():
            assert response.headers.get(header) == expected, header

    def test_headers_present_on_error_responses(self, client):
        response = client.get("/api/unknown")
        for header, expected in self.REQUIRED.items():
            assert response.headers.get(header) == expected, header

    def test_csp_forbids_framing_and_inline_scripts(self, client):
        csp = client.get("/api/config").headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        assert "default-src 'self'" in csp

    def test_server_banner_is_masked(self, client):
        """No server version may be disclosed."""
        server = client.get("/api/health").headers.get("Server", "")
        assert "Werkzeug" not in server
        assert "/" not in server

    def test_hsts_present_only_in_production(self, client, production_app):
        assert "Strict-Transport-Security" not in client.get("/api/health").headers

        with production_app.test_client() as prod_client:
            hsts = prod_client.get("/api/health").headers.get("Strict-Transport-Security", "")
            assert "max-age=" in hsts


# ===========================================================================
# A02:2021 — Cryptographic Failures (cookies / secrets)
# ===========================================================================


class TestSessionHardening:
    def test_session_cookie_is_httponly_and_samesite(self, app):
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] in {"Lax", "Strict"}

    def test_production_forces_secure_cookies(self, production_app):
        assert production_app.config["SESSION_COOKIE_SECURE"] is True

    def test_production_does_not_ship_a_default_secret(self, tmp_path):
        """In production, no weak fallback key may exist."""
        import os

        from app import create_app
        from app.config import ProductionConfig

        previous = os.environ.pop("LOTO_SECRET_KEY", None)
        try:

            class Cfg(ProductionConfig):
                DATABASE_PATH = str(tmp_path / "nosecret.db")

            app = create_app(Cfg)
            assert not app.config["SECRET_KEY"]
        finally:
            if previous is not None:
                os.environ["LOTO_SECRET_KEY"] = previous
            else:
                os.environ.setdefault("LOTO_SECRET_KEY", "restore-default")


# ===========================================================================
# A03:2021 — Injection (SQL / JSON / types)
# ===========================================================================


class TestInjectionResistance:
    def test_sql_injection_in_query_param_is_rejected(self, client):
        payload = "1; DROP TABLE draws;--"
        response = client.get(f"/api/draws?limit={payload}")
        assert response.status_code == 400
        assert response.is_json

    def test_sql_injection_in_query_param_leaves_db_intact(self, client):
        client.get("/api/draws?limit=1%3B%20DROP%20TABLE%20draws%3B--")
        # The table must still answer normally.
        assert client.get("/api/draws?limit=1").status_code == 200
        assert client.get("/api/health").get_json()["draws"] > 0

    @pytest.mark.parametrize("malicious", ["5 OR 1=1", "../../etc/passwd", "0x10", "1e3", "-1"])
    def test_malformed_limit_values_are_rejected(self, client, malicious):
        response = client.get(f"/api/draws?limit={malicious}")
        assert response.status_code == 400

    def test_numbers_with_strings_are_rejected(self, client):
        response = client.post(
            "/api/simulate",
            json={"numbers": ["1", "2", "3", "4", "5"], "chance": 3},
        )
        assert response.status_code == 400

    def test_numbers_with_floats_are_rejected(self, client):
        response = client.post(
            "/api/simulate",
            json={"numbers": [1.5, 2.5, 3.5, 4.5, 5.5], "chance": 3},
        )
        assert response.status_code == 400

    def test_numbers_with_booleans_are_rejected(self, client):
        response = client.post(
            "/api/simulate",
            json={"numbers": [True, False, True, False, True], "chance": 3},
        )
        assert response.status_code == 400

    def test_sql_keyword_in_string_field_is_not_executed(self, client, valid_payload):
        # The number field is not an executable string: it must be rejected.
        response = client.post(
            "/api/simulate",
            json={**valid_payload, "numbers": ["'; DROP TABLE simulations;--"]},
        )
        assert response.status_code == 400
        assert client.get("/api/simulations").status_code == 200


# ===========================================================================
# A04:2021 — Insecure Design / API4:2023 — Resource Consumption
# ===========================================================================


class TestResourceConsumption:
    def test_max_content_length_is_configured(self, app):
        assert app.config["MAX_CONTENT_LENGTH"] <= 1024 * 1024

    def test_oversized_numbers_list_is_rejected(self, client):
        response = client.post(
            "/api/simulate",
            json={"numbers": list(range(1, 500)), "chance": 3},
        )
        assert response.status_code == 400

    def test_limit_upper_bound_is_enforced(self, client):
        assert client.get("/api/draws?limit=500").status_code == 200
        assert client.get("/api/draws?limit=501").status_code == 400

    def test_negative_offset_is_rejected(self, client):
        assert client.get("/api/draws?offset=-1").status_code == 400

    def test_rate_limit_is_registered_on_simulate(self):
        """The expensive endpoint must be rate limited by default."""
        from app.config import Config

        assert Config.RATELIMIT_ENABLED is True
        assert "minute" in Config.RATELIMIT_SIMULATE

    def test_oversized_body_is_rejected_with_413(self, client):
        """An oversized body must be rejected before any processing."""
        huge = "x" * (128 * 1024)
        response = client.post(
            "/api/simulate",
            json={"numbers": [1, 2, 3, 4, 5], "chance": 3, "padding": huge},
        )
        assert response.status_code == 413

    def test_pdf_export_is_rate_limited(self):
        """The PDF export (expensive) has its own rate limit."""
        from app.config import Config

        assert "minute" in Config.RATELIMIT_PDF


# ===========================================================================
# A03/A05 — PDF export: injection and headers
# ===========================================================================


class TestPdfExportSecurity:
    def test_pdf_endpoint_rejects_injection_attempts(self, client):
        response = client.post(
            "/api/simulate/pdf",
            json={"numbers": ["1; DROP TABLE draws;--"] * 5, "chance": 3},
        )
        assert response.status_code == 400
        assert client.get("/api/health").get_json()["draws"] > 0

    def test_pdf_response_is_not_cacheable(self, client, valid_payload):
        """The report contains request data: no caching."""
        response = client.post("/api/simulate/pdf", json=valid_payload)
        assert response.headers.get("Cache-Control") == "no-store"

    def test_pdf_response_has_security_headers(self, client, valid_payload):
        response = client.post("/api/simulate/pdf", json=valid_payload)
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_pdf_content_type_cannot_be_confused(self, client, valid_payload):
        """The announced MIME type must not be HTML (anti-XSS)."""
        response = client.post("/api/simulate/pdf", json=valid_payload)
        content_type = response.headers.get("Content-Type", "")
        assert content_type.startswith("application/pdf")
        assert "html" not in content_type.lower()

    def test_pdf_filename_cannot_inject_headers(self, client):
        """A filename must never allow injecting a header."""
        response = client.post(
            "/api/simulate/pdf",
            json={"numbers": [1, 2, 3, 4, 5], "chance": 3},
        )
        disposition = response.headers.get("Content-Disposition", "")
        assert "\r" not in disposition
        assert "\n" not in disposition


# ===========================================================================
# A05:2021 — Security Misconfiguration
# ===========================================================================


class TestMisconfiguration:
    def test_debug_is_disabled_by_default(self, app):
        assert app.config["DEBUG"] is False

    def test_cors_uses_an_allowlist_not_wildcard(self, app):
        assert "*" not in app.config["CORS_ORIGINS"]

    def test_disallowed_origin_gets_no_cors_grant(self, client):
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert response.headers.get("Access-Control-Allow-Origin") != "https://evil.example"

    def test_allowed_origin_is_granted(self, app):
        with app.test_client() as test_client:
            response = test_client.get(
                "/api/health", headers={"Origin": app.config["CORS_ORIGINS"][0]}
            )
            assert response.headers.get("Access-Control-Allow-Origin") == app.config["CORS_ORIGINS"][0]

    def test_error_does_not_leak_stack_trace(self, client):
        response = client.post(
            "/api/simulate",
            data="{ invalid json",
            content_type="application/json",
        )
        body = response.get_data(as_text=True)
        assert response.status_code == 400
        assert "Traceback" not in body
        assert "File \"" not in body


# ===========================================================================
# A07:2021 — Identification and Authentication Failures
# ===========================================================================


class TestAuthenticationSurface:
    def test_no_endpoint_exposes_credentials(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "password" not in body.lower()
        assert "secret" not in body.lower()

    def test_error_messages_do_not_reveal_internal_details(self, client):
        response = client.get("/api/draws?limit=abc")
        body = response.get_json()
        assert set(body) == {"error"}
        assert "sqlite" not in json.dumps(body).lower()


# ===========================================================================
# A09:2021 — Security Logging and Monitoring Failures
# ===========================================================================


class TestObservability:
    def test_health_endpoint_available_for_monitoring(self, client):
        health = client.get("/api/health").get_json()
        assert health["status"] == "ok"
        assert "draws" in health

    def test_rate_limit_returns_429_when_exceeded(self, tmp_path):
        """With a tiny limit, the server must answer 429."""
        from app import create_app
        from app.config import Config

        class Cfg(Config):
            DATABASE_PATH = str(tmp_path / "limited.db")
            TESTING = True
            RATELIMIT_ENABLED = True
            RATELIMIT_SIMULATE = "1 per minute"
            RATELIMIT_DEFAULT = "1 per minute"

        app = create_app(Cfg)
        with app.test_client() as limited_client:
            payload = {"numbers": [1, 2, 3, 4, 5], "chance": 3, "persist": False}
            limited_client.post("/api/simulate", json=payload)
            second = limited_client.post("/api/simulate", json=payload)
            assert second.status_code == 429
            assert "Retry-After" in second.headers or second.is_json
