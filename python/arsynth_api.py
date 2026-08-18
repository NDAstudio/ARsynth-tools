"""ARSynth Supabase HTTP client.

Standard library only, so it runs inside TouchDesigner without installing
anything. Knows nothing about TouchDesigner — it can be imported and tested
from a plain Python shell.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def ssl_context() -> ssl.SSLContext:
    """A context that can actually verify certificates inside TouchDesigner.

    TouchDesigner's bundled Python does not read the macOS keychain, so the
    default context fails every HTTPS request with CERTIFICATE_VERIFY_FAILED.
    certifi ships with TouchDesigner and carries its own CA bundle, so this
    verifies properly rather than switching verification off.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class ArsynthApiError(Exception):
    """Any failure talking to Supabase."""


class TokenExpiredError(ArsynthApiError):
    """HTTP 401 — the access token needs refreshing."""


@dataclass
class Session:
    access_token: str
    refresh_token: str
    expires_at: float
    user_email: str
    user_id: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def as_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "user_email": self.user_email,
            "user_id": self.user_id,
        }

    @classmethod
    def from_auth_response(cls, payload: dict[str, Any]) -> "Session":
        user = payload.get("user") or {}
        expires_in = float(payload.get("expires_in", 3600))
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            # 30s of slack so a request started just before expiry still lands
            expires_at=time.time() + expires_in - 30,
            user_email=user.get("email", ""),
            user_id=user.get("id", ""),
        )


class ArsynthClient:
    """Talks to the Supabase auth and REST endpoints behind ARSynth."""

    def __init__(self, supabase_url: str, anon_key: str, *,
                 user_agent: str = "ARsynth_control") -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.anon_key = anon_key
        self.user_agent = user_agent
        self._ssl_context = ssl_context()

    # -- transport ---------------------------------------------------------

    def _request(self, method: str, path: str, *, body: dict | None = None,
                 token: str | None = None) -> Any:
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.supabase_url}{path}", data=data, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=15,
                                        context=self._ssl_context) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            message = self._error_message(exc)
            if exc.code == 401:
                raise TokenExpiredError(message) from exc
            raise ArsynthApiError(f"HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ArsynthApiError(f"Network error: {exc.reason}") from exc

    @staticmethod
    def _error_message(exc: urllib.error.HTTPError) -> str:
        detail = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            return detail
        for key in ("msg", "message", "error_description", "error"):
            if parsed.get(key):
                return str(parsed[key])
        return detail

    # -- auth --------------------------------------------------------------

    def login(self, email: str, password: str) -> Session:
        payload = self._request(
            "POST", "/auth/v1/token?grant_type=password",
            body={"email": email, "password": password},
            token=self.anon_key,
        )
        return Session.from_auth_response(payload)

    def refresh(self, session: Session) -> Session:
        payload = self._request(
            "POST", "/auth/v1/token?grant_type=refresh_token",
            body={"refresh_token": session.refresh_token},
            token=self.anon_key,
        )
        return Session.from_auth_response(payload)

    # -- data --------------------------------------------------------------

    def list_shows(self, session: Session) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/rest/v1/shows?select=id,title,active_scene&user_id=eq.{session.user_id}",
            token=session.access_token,
        ) or []

    def list_scenes(self, session: Session) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/rest/v1/scenes?select=id,title&user_id=eq.{session.user_id}",
            token=session.access_token,
        ) or []

    def set_active_scene(self, session: Session, show_id: str, scene_id: str) -> None:
        self._request(
            "PATCH", f"/rest/v1/shows?id=eq.{show_id}",
            body={"active_scene": scene_id},
            token=session.access_token,
        )
