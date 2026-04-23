"""OAuth2 authentication helpers for Skribo Teams creation scripts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional


TOKEN_SERVICE_NAME = "skribo"
TOKEN_USERNAME = "skribo-m365-access-token"
LINUX_TOKEN_FILENAME = ".skribo_access_token"
MICROSOFT_AUTH_BASE_URL = "https://login.microsoftonline.com"
MICROSOFT_TENANT_COMMON = "organizations"
DEFAULT_CLIENT_ID = "78362060-8853-4796-ae3f-0071241f0d3b"
DEFAULT_MICROSOFT_SCOPE = "https://graph.microsoft.com/.default"
DEFAULT_CALLBACK_PORT = 8765


class AuthError(RuntimeError):
    """Raised when OAuth2 authentication fails."""


class TokenStorageError(RuntimeError):
    """Raised when secure token storage fails."""


@dataclass(frozen=True)
class OAuth2Config:
    client_id: str
    authorization_url: str
    token_url: str
    scopes: list[str]


@dataclass(frozen=True)
class OAuth2Result:
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_in: Optional[int]


def create_microsoft_common_config(
    scopes: Optional[list[str]] = None,
    client_id: str = DEFAULT_CLIENT_ID,
) -> OAuth2Config:
    """Create OAuth2 config for Microsoft Entra ID 'common' tenant."""
    base = f"{MICROSOFT_AUTH_BASE_URL}/{MICROSOFT_TENANT_COMMON}/oauth2/v2.0"
    effective_scopes = scopes or [DEFAULT_MICROSOFT_SCOPE]
    return OAuth2Config(
        client_id=client_id,
        authorization_url=f"{base}/authorize",
        token_url=f"{base}/token",
        scopes=effective_scopes,
    )


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    oauth_code: Optional[str] = None
    oauth_error: Optional[str] = None
    oauth_state: Optional[str] = None
    expected_state: Optional[str] = None
    callback_event = threading.Event()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        state = query.get("state", [None])[0]
        if self.expected_state and state != self.expected_state:
            self._respond_html(
                400,
                "<h1>Authentication failed</h1><p>Invalid state.</p>",
            )
            self.__class__.oauth_error = "Invalid OAuth2 state in callback."
            self.__class__.callback_event.set()
            return

        error = query.get("error", [None])[0]
        if error:
            self._respond_html(
                400,
                f"<h1>Authentication failed</h1><p>{error}</p>",
            )
            self.__class__.oauth_error = error
            self.__class__.callback_event.set()
            return

        code = query.get("code", [None])[0]
        if not code:
            self._respond_html(
                400,
                "<h1>Authentication failed</h1><p>Missing authorization code.</p>",
            )
            self.__class__.oauth_error = "Missing authorization code."
            self.__class__.callback_event.set()
            return

        self._respond_html(
            200,
            "<h1>Authentication successful</h1><p>You can close this window now.</p>",
        )
        self.__class__.oauth_code = code
        self.__class__.oauth_state = state
        self.__class__.callback_event.set()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Silence default HTTP request logging in CLI output.
        return

    def _respond_html(self, status: int, content: str) -> None:
        body = f"<!doctype html><html><body>{content}</body></html>".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode("ascii").rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return verifier, challenge


def _open_oauth_browser(url: str) -> None:
    if webbrowser.open(url, new=1):
        return

    if sys.platform == "darwin":
        subprocess.run(["open", url], check=True)
        return

    if sys.platform.startswith("win"):
        os.startfile(url)  # type: ignore[attr-defined]  # noqa: PTH123
        return

    subprocess.run(["xdg-open", url], check=True)


def _linux_token_path() -> Path:
    return Path(os.getcwd()) / LINUX_TOKEN_FILENAME


def save_access_token(token: str) -> None:
    """Save access token securely per platform."""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError as exc:
            raise TokenStorageError(
                "Missing dependency 'keyring'. Install with: pip install keyring"
            ) from exc

        try:
            keyring.set_password(TOKEN_SERVICE_NAME, TOKEN_USERNAME, token)
        except Exception as exc:  # pragma: no cover - backend-specific failures
            raise TokenStorageError(f"Failed to store token in system key store: {exc}") from exc
        return

    token_path = _linux_token_path()
    fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)
    finally:
        os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)


def load_access_token() -> Optional[str]:
    """Load saved access token from secure storage."""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError as exc:
            raise TokenStorageError(
                "Missing dependency 'keyring'. Install with: pip install keyring"
            ) from exc

        try:
            return keyring.get_password(TOKEN_SERVICE_NAME, TOKEN_USERNAME)
        except Exception as exc:  # pragma: no cover - backend-specific failures
            raise TokenStorageError(f"Failed to read token from system key store: {exc}") from exc

    token_path = _linux_token_path()
    if not token_path.exists():
        return None
    return token_path.read_text(encoding="utf-8").strip() or None


def delete_access_token() -> None:
    """Delete the stored access token."""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError as exc:
            raise TokenStorageError(
                "Missing dependency 'keyring'. Install with: pip install keyring"
            ) from exc

        try:
            keyring.delete_password(TOKEN_SERVICE_NAME, TOKEN_USERNAME)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:  # pragma: no cover - backend-specific failures
            raise TokenStorageError(f"Failed to delete token from system key store: {exc}") from exc
        return

    token_path = _linux_token_path()
    if token_path.exists():
        token_path.unlink()


def authenticate_and_store_token(
    config: OAuth2Config,
    timeout_seconds: int = 300,
    show_auth_url: bool = False,
    require_browser_confirmation: bool = False,
) -> OAuth2Result:
    """Run OAuth2 Authorization Code with PKCE and persist the access token."""
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)

    _OAuthCallbackHandler.oauth_code = None
    _OAuthCallbackHandler.oauth_error = None
    _OAuthCallbackHandler.oauth_state = None
    _OAuthCallbackHandler.expected_state = state
    _OAuthCallbackHandler.callback_event.clear()

    try:
        server = HTTPServer(("localhost", DEFAULT_CALLBACK_PORT), _OAuthCallbackHandler)
    except OSError as exc:
        raise AuthError(
            f"Callback port {DEFAULT_CALLBACK_PORT} is unavailable. "
            "Close the blocking process and try again."
        ) from exc
    redirect_uri = f"http://localhost:{server.server_port}/callback"

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    query = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{config.authorization_url}?{urllib.parse.urlencode(query)}"

    if show_auth_url:
        print(f"OAuth2 URL: {auth_url}")

    if require_browser_confirmation:
        try:
            input("Press Enter to open the browser for OAuth2 login...")
        except EOFError as exc:
            server.server_close()
            raise AuthError("No interactive input available for browser confirmation.") from exc

    try:
        _open_oauth_browser(auth_url)
    except Exception as exc:
        server.server_close()
        raise AuthError(f"Unable to open OAuth2 browser window: {exc}") from exc

    if not _OAuthCallbackHandler.callback_event.wait(timeout=timeout_seconds):
        server.server_close()
        raise AuthError("Timed out waiting for OAuth2 callback.")

    server.server_close()

    if _OAuthCallbackHandler.oauth_error:
        raise AuthError(f"OAuth2 callback returned error: {_OAuthCallbackHandler.oauth_error}")

    auth_code = _OAuthCallbackHandler.oauth_code
    if not auth_code:
        raise AuthError("OAuth2 callback did not include an authorization code.")

    token_payload = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": config.client_id,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        config.token_url,
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token_response = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AuthError(f"Token endpoint returned HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise AuthError(f"Token exchange failed: {exc}") from exc

    access_token = token_response.get("access_token")
    if not access_token:
        raise AuthError("Token response does not include an access token.")

    save_access_token(access_token)

    return OAuth2Result(
        access_token=access_token,
        refresh_token=token_response.get("refresh_token"),
        token_type=token_response.get("token_type", "Bearer"),
        expires_in=token_response.get("expires_in"),
    )


def authenticate_with_microsoft_common(
    scopes: Optional[list[str]] = None,
    client_id: str = DEFAULT_CLIENT_ID,
    timeout_seconds: int = 300,
    show_auth_url: bool = False,
    require_browser_confirmation: bool = False,
) -> OAuth2Result:
    """Authenticate against Microsoft 'common' tenant without client secret.

    If no scopes are provided, Graph default scope is used.
    """
    config = create_microsoft_common_config(scopes=scopes, client_id=client_id)
    return authenticate_and_store_token(
        config=config,
        timeout_seconds=timeout_seconds,
        show_auth_url=show_auth_url,
        require_browser_confirmation=require_browser_confirmation,
    )
