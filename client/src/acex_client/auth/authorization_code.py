import hashlib
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from . import token_store
from .provider import AuthProvider

_CALLBACK_PORT = 9876
_REDIRECT_URI = f"http://localhost:{_CALLBACK_PORT}/callback"


class AuthorizationCodeAuth(AuthProvider):
    def __init__(self, client_id: str, issuer_url: str):
        self._client_id = client_id
        oidc = self._discover(issuer_url)
        self._auth_url = oidc["authorization_endpoint"]
        self._token_url = oidc["token_endpoint"]

    def get_token(self) -> str:
        data = token_store.load()
        if data and not token_store.is_expired(data):
            return data["access_token"]
        if data and data.get("refresh_token"):
            try:
                return self._refresh(data["refresh_token"])
            except Exception:
                pass
        return self._interactive_login()

    def _interactive_login(self) -> str:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            hashlib.sha256(code_verifier.encode()).digest()
        )
        import base64
        code_challenge_b64 = base64.urlsafe_b64encode(code_challenge).rstrip(b"=").decode()

        auth_params = urlencode({
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": _REDIRECT_URI,
            "scope": "openid profile email",
            "code_challenge": code_challenge_b64,
            "code_challenge_method": "S256",
        })
        login_url = f"{self._auth_url}?{auth_params}"

        code = self._wait_for_callback(login_url)

        resp = requests.post(
            self._token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "code": code,
                "redirect_uri": _REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return self._store_and_return(resp.json())

    def _refresh(self, refresh_token: str) -> str:
        resp = requests.post(
            self._token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return self._store_and_return(resp.json())

    def _store_and_return(self, data: dict) -> str:
        token_store.save({
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": time.time() + data.get("expires_in", 300),
        })
        return data["access_token"]

    @staticmethod
    def _wait_for_callback(login_url: str) -> str:
        auth_code: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                params = parse_qs(urlparse(self.path).query)
                code = params.get("code", [None])[0]
                if code:
                    auth_code.append(code)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Login successful. You can close this tab.")

            def log_message(self, *args):
                pass

        server = HTTPServer(("localhost", _CALLBACK_PORT), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        print(f"Opening browser for login...\n{login_url}")
        webbrowser.open(login_url)

        while not auth_code:
            time.sleep(0.2)

        server.shutdown()
        return auth_code[0]

    @staticmethod
    def _discover(issuer_url: str) -> dict:
        url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()
