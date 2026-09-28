"""Panasonic Smart China cloud API client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
from typing import Any

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import PanasonicEndpoint, PanasonicProfile

BASE_URL = "https://app.psmartcloud.com/App"
URL_LOGIN = f"{BASE_URL}/UsrLogin"
URL_GET_DEV = f"{BASE_URL}/UsrGetBindDevInfo"
URL_GET_TOKEN = f"{BASE_URL}/UsrGetToken"

AUTH_ERROR_CODES = {"3003", "3004", "403", "4102"}
SUCCESS_ERROR_CODES = {None, "", 0, "0", "0000"}
REQUEST_ATTEMPTS = 3
RETRY_DELAYS = (0.75, 2.0)


class PanasonicApiError(Exception):
    """Base exception for Panasonic cloud API failures."""


class PanasonicApiAuthError(PanasonicApiError):
    """Raised when the Panasonic session is expired or invalid."""


class PanasonicApiResponseError(PanasonicApiError):
    """Raised when the Panasonic cloud returns an invalid response."""


@dataclass(frozen=True)
class LoginResult:
    """Successful login result."""

    usr_id: str
    ssid: str
    family_id: str
    real_family_id: str
    devices: dict[str, dict[str, Any]]


class PanasonicApiClient:
    """Small async client for the reverse engineered Panasonic cloud API."""

    def __init__(self, hass: HomeAssistant, ssid: str | None = None) -> None:
        self._hass = hass
        self.ssid = ssid

    async def authenticate(self, username: str, password: str) -> LoginResult:
        """Run the full login flow and return the account devices."""
        token_res = await self._post(
            URL_GET_TOKEN,
            {
                "id": 1,
                "uiVersion": 4.0,
                "params": {"usrId": username},
            },
            headers=self._app_headers(),
            require_results=True,
        )
        token_start = token_res["results"].get("token")
        if not token_start:
            raise PanasonicApiResponseError("GetToken response did not include token")

        pwd_md5 = hashlib.md5(password.encode()).hexdigest().upper()
        inter_md5 = hashlib.md5(f"{pwd_md5}{username}".encode()).hexdigest().upper()
        final_token = hashlib.md5(f"{inter_md5}{token_start}".encode()).hexdigest().upper()

        login_res = await self._post(
            URL_LOGIN,
            {
                "id": 2,
                "uiVersion": 4.0,
                "params": {
                    "telId": "00:00:00:00:00:00",
                    "checkFailCount": 0,
                    "usrId": username,
                    "pwd": final_token,
                },
            },
            headers=self._app_headers(),
            require_results=True,
        )
        results = login_res["results"]
        usr_id = results["usrId"]
        ssid = results["ssId"]
        family_id = results["familyId"]
        real_family_id = results["realFamilyId"]

        self.ssid = ssid
        devices = await self.get_devices(usr_id, family_id, real_family_id)
        return LoginResult(
            usr_id=usr_id,
            ssid=ssid,
            family_id=family_id,
            real_family_id=real_family_id,
            devices=devices,
        )

    async def get_devices(
        self, usr_id: str, family_id: str, real_family_id: str
    ) -> dict[str, dict[str, Any]]:
        """Return all bound devices for the current account session."""
        res = await self._post(
            URL_GET_DEV,
            {
                "id": 3,
                "uiVersion": 4.0,
                "params": {
                    "realFamilyId": real_family_id,
                    "familyId": family_id,
                    "usrId": usr_id,
                },
            },
            headers=self._app_headers(include_cookie=True),
            require_results=True,
        )

        devices = {}
        for dev in res["results"].get("devList", []):
            device_id = dev.get("deviceId")
            params = dev.get("params")
            if device_id and isinstance(params, dict):
                devices[device_id] = params
        return devices

    async def get_device_status(
        self,
        profile: PanasonicProfile,
        usr_id: str,
        device_id: str,
        token: str,
    ) -> dict[str, Any]:
        """Fetch the latest status for a supported device profile."""
        endpoint = profile.status_endpoint
        res = await self._post(
            self._endpoint_url(endpoint),
            {
                "id": endpoint.request_id,
                "usrId": usr_id,
                "deviceId": device_id,
                "token": token,
            },
            headers=self._control_headers(profile, device_id),
            require_results=endpoint.require_results,
            allow_non_json_response=endpoint.allow_non_json_response,
        )

        results = res.get("results") if endpoint.require_results else res.get("results", res)
        if not isinstance(results, dict):
            raise PanasonicApiResponseError("Status response results must be an object")
        missing_keys = endpoint.required_result_keys - results.keys()
        if missing_keys:
            raise PanasonicApiResponseError(
                f"Status response did not include required keys: {sorted(missing_keys)}"
            )
        return results

    async def set_device_status(
        self,
        profile: PanasonicProfile,
        usr_id: str,
        device_id: str,
        token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Send status/control params for a supported device profile."""
        endpoint = profile.set_endpoint
        return await self._post(
            self._endpoint_url(endpoint),
            {
                "id": endpoint.request_id,
                "usrId": usr_id,
                "deviceId": device_id,
                "token": token,
                "params": params,
            },
            headers=self._control_headers(profile, device_id),
            require_results=endpoint.require_results,
            allow_non_json_response=endpoint.allow_non_json_response,
        )

    async def _post(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
        require_results: bool,
        allow_non_json_response: bool = False,
    ) -> dict[str, Any]:
        for attempt in range(REQUEST_ATTEMPTS):
            try:
                return await self._post_once(
                    url,
                    payload,
                    headers=headers,
                    require_results=require_results,
                    allow_non_json_response=allow_non_json_response,
                )
            except PanasonicApiAuthError:
                raise
            except PanasonicApiResponseError:
                if attempt == REQUEST_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(RETRY_DELAYS[attempt])

        raise PanasonicApiResponseError(f"Request failed after retries: {url}")

    async def _post_once(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
        require_results: bool,
        allow_non_json_response: bool = False,
    ) -> dict[str, Any]:
        session = async_get_clientsession(self._hass)
        try:
            async with async_timeout.timeout(10):
                response = await session.post(url, json=payload, headers=headers, ssl=False)
                if response.status != 200:
                    text = await response.text()
                    raise PanasonicApiResponseError(
                        f"HTTP {response.status} from {url}: {text[:200]}"
                    )

                try:
                    data = await response.json()
                except Exception as err:
                    text = await response.text()
                    if allow_non_json_response:
                        for auth_code in AUTH_ERROR_CODES:
                            if auth_code in text:
                                raise PanasonicApiAuthError(
                                    f"Panasonic session expired (errorCode: {auth_code})"
                                ) from err
                        return {}
                    raise PanasonicApiResponseError(
                        f"Invalid JSON from {url}: {text[:200]}"
                    ) from err
        except PanasonicApiError:
            raise
        except TimeoutError as err:
            raise PanasonicApiResponseError(f"Request timed out: {url}") from err
        except Exception as err:
            raise PanasonicApiResponseError(f"Request failed: {url}: {err}") from err

        if not isinstance(data, dict):
            raise PanasonicApiResponseError(f"Unexpected JSON response from {url}")

        self._raise_for_business_error(data)
        if require_results and "results" not in data:
            raise PanasonicApiResponseError(f"Missing results in response from {url}")
        return data

    def _raise_for_business_error(self, data: dict[str, Any]) -> None:
        nested_error = data.get("error")
        nested_error = nested_error if isinstance(nested_error, dict) else {}
        error_code = data.get("errorCode", nested_error.get("code"))
        if error_code in SUCCESS_ERROR_CODES:
            return

        error_code_text = str(error_code)
        message = (
            data.get("errorMessage")
            or data.get("msg")
            or nested_error.get("message")
            or "Panasonic API error"
        )
        if error_code_text in AUTH_ERROR_CODES:
            raise PanasonicApiAuthError(f"{message} (errorCode: {error_code_text})")
        raise PanasonicApiResponseError(f"{message} (errorCode: {error_code_text})")

    def _app_headers(self, include_cookie: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": "SmartApp",
            "Content-Type": "application/json",
        }
        if include_cookie and self.ssid:
            headers["Cookie"] = f"SSID={self.ssid}"
        return headers

    def _endpoint_url(self, endpoint: PanasonicEndpoint) -> str:
        return f"{BASE_URL}/{endpoint.path}"

    def _control_headers(
        self,
        profile: PanasonicProfile | None = None,
        device_id: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X)",
            "xtoken": f"SSID={self.ssid}",
            "DNT": "1",
            "Origin": "https://app.psmartcloud.com",
            "X-Requested-With": "XMLHttpRequest",
        }
        if profile and profile.cookie_required and self.ssid:
            headers["Cookie"] = f"SSID={self.ssid}"
        if profile and profile.referer_template:
            headers["Referer"] = profile.referer_template.format(
                device_id=device_id or "",
                controller_model=profile.controller_model,
                profile_id=profile.profile_id,
            )
        if profile:
            headers.update(profile.extra_control_headers)
        return headers
