"""Small async client for the (unofficial) DHL app endpoints.

Ported from ioBroker.parcel (https://github.com/TA2k/ioBroker.parcel, MIT).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from yarl import URL

from .const import (
    ADVICES_URL,
    AKAMAI_COOKIES,
    APP_USER_AGENT,
    BASIC_AUTH,
    CLIENT_ID,
    CODE_VERIFIER,
    IMAGE_USER_AGENT,
    REDIRECT_URI,
    SEARCH_URL,
    TOKEN_URL,
    WEB_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
TIMEOUT = aiohttp.ClientTimeout(total=20)


class DhlAuthError(Exception):
    """Login / token refresh failed - user must log in again."""


class DhlApiError(Exception):
    """Temporary communication problem."""


def extract_code(dhl_login_url: str) -> str:
    """Return the OAuth code from a dhllogin://...?code=... URL (or a bare code)."""
    text = dhl_login_url.strip()
    if "code=" not in text:
        if text and "://" not in text and " " not in text:
            return text
        raise ValueError("no code")
    query = text.split("?", 1)[1] if "?" in text else text
    code = parse_qs(query).get("code", [None])[0]
    if not code:
        raise ValueError("no code")
    return code


def decode_jwt_claims(token: str | None) -> dict[str, Any]:
    """Decode JWT payload without verification (only used for display/unique id)."""
    if not token:
        return {}
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}


def decrypt_letter_image(url: str, data: bytes) -> bytes:
    """Decrypt a Briefankündigung image (AES-GCM, key derived from URL uuid)."""
    uuid = urlparse(url).path.rsplit("/", 1)[-1]
    digest = hashlib.sha512(uuid.encode()).digest()
    key, iv, aad = digest[0:32], digest[32:44], digest[44:56]
    return AESGCM(key).decrypt(iv, data, aad)


class DhlClient:
    """DHL client keeping tokens and cookies."""

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str | None = None) -> None:
        self._session = session
        self.refresh_token = refresh_token
        self.id_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ auth
    async def async_login_with_code(self, code: str) -> dict[str, Any]:
        """Exchange the authorization code for tokens."""
        data = {
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": CODE_VERIFIER,
            "code": code,
        }
        return await self._token_request(data, basic_auth=True)

    async def async_refresh(self) -> dict[str, Any]:
        """Refresh the tokens."""
        if not self.refresh_token:
            raise DhlAuthError("no refresh token")
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        return await self._token_request(data, basic_auth=False)

    async def async_ensure_token(self) -> None:
        """Refresh the token when it (nearly) expired."""
        async with self._lock:
            if self.id_token and time.time() < self._expires_at - 120:
                return
            await self.async_refresh()

    async def _token_request(self, data: dict[str, str], basic_auth: bool) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://login.dhl.de",
            "User-Agent": APP_USER_AGENT,
            "Accept-Language": "de-de",
        }
        if basic_auth:
            headers["Authorization"] = BASIC_AUTH
        try:
            async with self._session.post(TOKEN_URL, data=data, headers=headers, timeout=TIMEOUT) as resp:
                text = await resp.text()
                if resp.status in (400, 401, 403):
                    _LOGGER.debug("DHL token error %s: %s", resp.status, text)
                    raise DhlAuthError(f"token request rejected ({resp.status})")
                if resp.status >= 300:
                    raise DhlApiError(f"token request failed ({resp.status}): {text[:200]}")
                result = json.loads(text)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DhlApiError(f"token request failed: {err}") from err
        except json.JSONDecodeError as err:
            raise DhlApiError("invalid token response") from err

        if "id_token" not in result:
            raise DhlAuthError("no id_token in response")
        self.id_token = result["id_token"]
        self.refresh_token = result.get("refresh_token", self.refresh_token)
        self._expires_at = time.time() + int(result.get("expires_in", 1800))
        self._set_cookie()
        return result

    def _set_cookie(self) -> None:
        cookie = SimpleCookie()
        cookie["dhli"] = self.id_token or ""
        cookie["dhli"]["domain"] = ".dhl.de"
        cookie["dhli"]["path"] = "/"
        self._session.cookie_jar.update_cookies(cookie, URL("https://www.dhl.de/"))

    # ------------------------------------------------------------------ data
    def _clear_akamai(self) -> None:
        self._session.cookie_jar.clear(lambda morsel: morsel.key in AKAMAI_COOKIES)

    async def _get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": WEB_USER_AGENT,
            "accept-language": "de-de",
        }
        try:
            async with self._session.get(url, params=params, headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    self._expires_at = 0  # force refresh next time
                    raise DhlApiError(f"401 for {url}")
                if resp.status >= 300:
                    raise DhlApiError(f"HTTP {resp.status} for {url}")
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DhlApiError(f"request to {url} failed: {err}") from err
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise DhlApiError(f"invalid JSON from {url}") from err

    async def async_get_shipments(self) -> list[dict[str, Any]]:
        """Return all non-archived shipments with details."""
        await self.async_ensure_token()
        self._clear_akamai()
        base = {"noRedirect": "true", "language": "de", "cid": "app"}
        overview = await self._get_json(SEARCH_URL, base)
        ids = [
            s["id"]
            for s in (overview or {}).get("sendungen", [])
            if s.get("sendungsinfo", {}).get("sendungsliste") != "ARCHIVIERT" and s.get("id")
        ]
        if not ids:
            return []
        details = await self._get_json(SEARCH_URL, {"piececode": ",".join(ids), **base})
        return [
            s
            for s in (details or {}).get("sendungen", [])
            if s.get("sendungsinfo", {}).get("sendungsliste") != "ARCHIVIERT"
        ]

    async def async_get_advices(self) -> dict[str, Any] | None:
        """Return Briefankündigung data (activates the access grant if needed)."""
        await self.async_ensure_token()
        for _ in range(2):
            data = await self._get_json(ADVICES_URL)
            if isinstance(data, dict) and data.get("grantToken") and data.get("accessTokenUrl"):
                await self._activate_grant(data["grantToken"], data["accessTokenUrl"])
                await asyncio.sleep(1)
                continue
            return data
        return None

    async def _activate_grant(self, grant_token: str, url: str) -> None:
        try:
            async with self._session.post(
                url,
                data=json.dumps({"grant_token": grant_token}),
                headers={"Accept": "*/*", "Content-Type": "application/json"},
                timeout=TIMEOUT,
            ) as resp:
                _LOGGER.debug("Grant activation: %s %s", resp.status, await resp.text())
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DhlApiError(f"grant activation failed: {err}") from err

    async def async_get_letter_image(self, url: str) -> bytes:
        """Download and decrypt a letter image."""
        try:
            await self.async_ensure_token()
        except DhlAuthError as err:
            raise DhlApiError("not logged in") from err
        try:
            async with self._session.get(
                url, headers={"User-Agent": IMAGE_USER_AGENT}, timeout=TIMEOUT
            ) as resp:
                if resp.status >= 300:
                    raise DhlApiError(f"image HTTP {resp.status}")
                raw = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DhlApiError(f"image download failed: {err}") from err
        try:
            return decrypt_letter_image(url, raw)
        except Exception as err:  # noqa: BLE001 - cryptography raises InvalidTag
            raise DhlApiError("image decryption failed") from err
