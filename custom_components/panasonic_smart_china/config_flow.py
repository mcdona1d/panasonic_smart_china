"""Config flow for Panasonic Smart China."""

from __future__ import annotations

import logging
from typing import Any, Mapping

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import PanasonicApiAuthError, PanasonicApiClient, PanasonicApiError
from .const import (
    CONF_CATEGORY,
    CONF_CONTROLLER_MODEL,
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICES,
    CONF_ENABLED,
    CONF_ENTITY_KIND,
    CONF_FAMILY_ID,
    CONF_HA_PLATFORMS,
    CONF_PROFILE_ID,
    CONF_REAL_FAMILY_ID,
    CONF_SENSOR_ID,
    CONF_SSID,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_USR_ID,
    DOMAIN,
    extract_category_from_device_id,
    find_controllers_for_category,
    find_controllers_for_device,
)
from .models import ENTITY_KIND_DUCTED_AC
from .token import DeviceTokenError, generate_device_token

_LOGGER = logging.getLogger(__name__)
RESCAN_DEVICES = "__rescan_devices__"
MODEL_FIELD_CANDIDATES = (
    "devSubTypeId",
    "devType",
    "deviceModel",
    "model",
    "modelName",
    "productModel",
)


class PanasonicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Account-level config flow."""

    VERSION = 2

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._usr_id: str | None = None
        self._ssid: str | None = None
        self._family_id: str | None = None
        self._real_family_id: str | None = None
        self._devices: dict[str, dict[str, Any]] = {}
        self._device_support_map: dict[str, dict[str, Any]] = {}

    async def async_step_user(self, user_input=None):
        """Log in to the Panasonic account."""
        errors = {}

        if user_input is not None:
            try:
                login = await PanasonicApiClient(self.hass).authenticate(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except PanasonicApiError as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not login.devices:
                    return self.async_abort(reason="no_devices_found")

                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                self._usr_id = login.usr_id
                self._ssid = login.ssid
                self._family_id = login.family_id
                self._real_family_id = login.real_family_id
                self._devices = login.devices
                self._analyze_device_support()

                await self.async_set_unique_id(login.usr_id)
                self._abort_if_unique_id_configured()

                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_devices(self, user_input=None):
        """Select supported devices to enable under this account."""
        errors = {}
        supported_devices = self._supported_devices()
        unsupported_devices = self._unsupported_device_summary()

        if not supported_devices:
            return self.async_abort(
                reason="no_supported_devices_found",
                description_placeholders={
                    "unsupported_devices": unsupported_devices,
                },
            )

        if user_input is not None:
            selected_device_ids = user_input.get(CONF_DEVICES, [])
            if not selected_device_ids:
                errors["base"] = "no_devices_selected"
            else:
                configured_devices = self._build_configured_devices(selected_device_ids)
                if not configured_devices:
                    errors["base"] = "no_devices_selected"
                else:
                    return self.async_create_entry(
                        title=f"松下账号 ({self._username})",
                        data={
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                            CONF_USR_ID: self._usr_id,
                            CONF_SSID: self._ssid,
                            CONF_FAMILY_ID: self._family_id,
                            CONF_REAL_FAMILY_ID: self._real_family_id,
                            CONF_DEVICES: configured_devices,
                        },
                    )

        options = [
            {
                "value": device_id,
                "label": _format_device_label(
                    info.get("deviceName", "Unknown"),
                    self._device_support_map.get(device_id, {}).get("model"),
                    device_id,
                ),
            }
            for device_id, info in supported_devices.items()
        ]

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICES,
                        default=list(supported_devices.keys()),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "unsupported_devices": unsupported_devices,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Start reauthentication for an existing account entry."""
        self._username = entry_data.get(CONF_USERNAME)
        self._usr_id = entry_data.get(CONF_USR_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for the account password and refresh the account session."""
        errors = {}

        if user_input is not None:
            try:
                login = await PanasonicApiClient(self.hass).authenticate(
                    self._username,
                    user_input[CONF_PASSWORD],
                )
            except PanasonicApiError as err:
                _LOGGER.error("Reauth failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                reauth_entry = self._get_reauth_entry()
                new_data = dict(reauth_entry.data)
                new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                new_data[CONF_USR_ID] = login.usr_id
                new_data[CONF_SSID] = login.ssid
                new_data[CONF_FAMILY_ID] = login.family_id
                new_data[CONF_REAL_FAMILY_ID] = login.real_family_id
                return self.async_update_reload_and_abort(reauth_entry, data=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Re-login and refresh the cloud session of an existing entry.

        Panasonic China only keeps one active session per account: when the
        phone App logs in again, the session stored in Home Assistant becomes
        invalid. This step lets the user refresh it from the entry menu
        (设置 -> 设备与服务 -> Panasonic Smart China -> 重新配置).
        """
        errors = {}
        entry = self._get_reconfigure_entry()
        username = entry.data.get(CONF_USERNAME) or self._username

        if user_input is not None:
            try:
                login = await PanasonicApiClient(self.hass).authenticate(
                    username,
                    user_input[CONF_PASSWORD],
                )
            except PanasonicApiError as err:
                _LOGGER.error("Reconfigure login failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                new_data = dict(entry.data)
                new_data[CONF_USERNAME] = username
                new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                new_data[CONF_USR_ID] = login.usr_id
                new_data[CONF_SSID] = login.ssid
                new_data[CONF_FAMILY_ID] = login.family_id
                new_data[CONF_REAL_FAMILY_ID] = login.real_family_id
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"username": username or ""},
        )

    def _analyze_device_support(self) -> None:
        self._device_support_map = {}
        for device_id, device_info in self._devices.items():
            category = extract_category_from_device_id(device_id)
            category_matches = find_controllers_for_category(category)
            matching = find_controllers_for_device(
                category,
                _extract_device_model_values(device_info, device_id),
            )
            if matching:
                unsupported_reason = None
            elif category_matches:
                unsupported_reason = "unsupported_model"
            else:
                unsupported_reason = "unsupported_category"
            self._device_support_map[device_id] = {
                "supported": bool(matching),
                "category": category,
                "model": _extract_device_model(
                    device_info,
                    _extract_device_id_suffix(device_id),
                ),
                "matching_controllers": matching,
                "unsupported_reason": unsupported_reason,
            }

    def _supported_devices(self) -> dict[str, dict[str, Any]]:
        return {
            device_id: info
            for device_id, info in self._devices.items()
            if self._device_support_map.get(device_id, {}).get("supported")
        }

    def _unsupported_device_summary(self) -> str:
        """Return a readable summary of devices filtered from the setup flow."""
        lines = []
        reason_labels = {
            "unsupported_category": "设备类别暂不支持",
            "unsupported_model": "设备型号暂不支持",
        }
        for device_id, device_info in self._devices.items():
            support_info = self._device_support_map.get(device_id, {})
            if support_info.get("supported"):
                continue
            name = device_info.get("deviceName", "Unknown")
            category = support_info.get("category") or "未识别"
            model = support_info.get("model") or "未识别"
            reason = reason_labels.get(
                support_info.get("unsupported_reason"),
                "设备暂不支持",
            )
            lines.append(f"- {name}：类别 {category}，型号 {model}，{reason}")
        return "\n".join(lines) if lines else "无"

    def _build_configured_devices(self, selected_device_ids: list[str]) -> dict[str, dict[str, Any]]:
        configured = {}
        for device_id in selected_device_ids:
            support_info = self._device_support_map.get(device_id, {})
            matching = support_info.get("matching_controllers", {})
            if not matching:
                continue

            profile = next(iter(matching.values()))
            dev_info = self._devices.get(device_id, {})
            device_model = _extract_device_model(dev_info, profile.controller_model)
            try:
                token = generate_device_token(device_id)
            except DeviceTokenError as err:
                _LOGGER.error("Token generation failed for deviceId %s: %s", device_id, err)
                continue

            configured[device_id] = {
                CONF_DEVICE_NAME: dev_info.get("deviceName", "Panasonic Device"),
                CONF_DEVICE_MODEL: device_model,
                CONF_CATEGORY: support_info.get("category"),
                CONF_CONTROLLER_MODEL: profile.controller_model,
                CONF_PROFILE_ID: profile.profile_id,
                CONF_HA_PLATFORMS: list(profile.ha_platforms),
                CONF_ENTITY_KIND: profile.entity_kind,
                CONF_TOKEN: token,
                CONF_SENSOR_ID: None,
                CONF_ENABLED: True,
            }
        return configured

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow for this handler."""
        return PanasonicOptionsFlow(config_entry)


class PanasonicOptionsFlow(config_entries.OptionsFlow):
    """Options flow for account-level device settings."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self._selected_device_id: str | None = None

    async def async_step_init(self, user_input=None):
        """Select a configured device to edit."""
        devices = self._config_entry.data.get(CONF_DEVICES, {})
        if not devices:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            self._selected_device_id = user_input[CONF_DEVICE_ID]
            if self._selected_device_id == RESCAN_DEVICES:
                return await self.async_step_rescan()
            return await self.async_step_edit_device()

        device_options = {
            RESCAN_DEVICES: "重新扫描账号设备",
            **{
                device_id: _format_device_label(
                    info.get(CONF_DEVICE_NAME, device_id),
                    info.get(CONF_DEVICE_MODEL) or info.get(CONF_CONTROLLER_MODEL),
                    device_id,
                )
                for device_id, info in devices.items()
            },
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(device_options)
                }
            ),
        )

    async def async_step_rescan(self, user_input=None):
        """Refresh account devices using the current account session."""
        data = self._config_entry.data
        devices = dict(data.get(CONF_DEVICES, {}))
        errors = {}

        try:
            cloud_devices = await PanasonicApiClient(self.hass, data.get(CONF_SSID)).get_devices(
                data[CONF_USR_ID],
                data[CONF_FAMILY_ID],
                data[CONF_REAL_FAMILY_ID],
            )
        except PanasonicApiAuthError as err:
            _LOGGER.warning("Panasonic session expired during device rescan: %s", err)
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={
                        "source": config_entries.SOURCE_REAUTH,
                        "entry_id": self._config_entry.entry_id,
                    },
                    data=self._config_entry.data,
                )
            )
            errors["base"] = "session_expired"
        except PanasonicApiError as err:
            _LOGGER.error("Device rescan failed: %s", err)
            errors["base"] = "cannot_connect"
        else:
            added = 0
            for device_id, device_info in cloud_devices.items():
                if device_id in devices:
                    devices[device_id][CONF_DEVICE_NAME] = device_info.get(
                        "deviceName",
                        devices[device_id].get(CONF_DEVICE_NAME, device_id),
                    )
                    category = devices[device_id].get(CONF_CATEGORY) or extract_category_from_device_id(
                        device_id
                    )
                    matching = find_controllers_for_device(
                        category,
                        _extract_device_model_values(device_info, device_id),
                    )
                    profile = next(iter(matching.values()), None)
                    devices[device_id][CONF_DEVICE_MODEL] = _extract_device_model(
                        device_info,
                        profile.controller_model
                        if profile
                        else devices[device_id].get(CONF_CONTROLLER_MODEL),
                    )
                    if profile:
                        devices[device_id][CONF_CATEGORY] = category
                        devices[device_id][CONF_CONTROLLER_MODEL] = profile.controller_model
                        devices[device_id][CONF_PROFILE_ID] = profile.profile_id
                        devices[device_id][CONF_HA_PLATFORMS] = list(profile.ha_platforms)
                        devices[device_id][CONF_ENTITY_KIND] = profile.entity_kind
                    continue

                category = extract_category_from_device_id(device_id)
                matching = find_controllers_for_device(
                    category,
                    _extract_device_model_values(device_info, device_id),
                )
                if not matching:
                    continue
                profile = next(iter(matching.values()))

                try:
                    token = generate_device_token(device_id)
                except DeviceTokenError as err:
                    _LOGGER.error("Token generation failed for deviceId %s: %s", device_id, err)
                    continue

                devices[device_id] = {
                    CONF_DEVICE_NAME: device_info.get("deviceName", "Panasonic Device"),
                    CONF_DEVICE_MODEL: _extract_device_model(
                        device_info,
                        profile.controller_model,
                    ),
                    CONF_CATEGORY: category,
                    CONF_CONTROLLER_MODEL: profile.controller_model,
                    CONF_PROFILE_ID: profile.profile_id,
                    CONF_HA_PLATFORMS: list(profile.ha_platforms),
                    CONF_ENTITY_KIND: profile.entity_kind,
                    CONF_TOKEN: token,
                    CONF_SENSOR_ID: None,
                    CONF_ENABLED: True,
                }
                added += 1

            new_data = dict(data)
            new_data[CONF_DEVICES] = devices
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            _LOGGER.info("Device rescan completed, added %s new supported devices.", added)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="rescan",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_edit_device(self, user_input=None):
        """Edit a single device under the account entry."""
        devices = dict(self._config_entry.data.get(CONF_DEVICES, {}))
        current = dict(devices[self._selected_device_id])

        if user_input is not None:
            if current.get(CONF_ENTITY_KIND) == ENTITY_KIND_DUCTED_AC:
                current[CONF_SENSOR_ID] = user_input.get(CONF_SENSOR_ID)
            current[CONF_ENABLED] = user_input[CONF_ENABLED]
            devices[self._selected_device_id] = current

            new_data = dict(self._config_entry.data)
            new_data[CONF_DEVICES] = devices
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = {
            vol.Required(CONF_ENABLED, default=current.get(CONF_ENABLED, True)): bool,
        }
        if current.get(CONF_ENTITY_KIND) == ENTITY_KIND_DUCTED_AC:
            schema[
                vol.Optional(
                    CONF_SENSOR_ID,
                    default=current.get(CONF_SENSOR_ID),
                )
            ] = EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="temperature")
            )

        return self.async_show_form(
            step_id="edit_device",
            description_placeholders={
                "device_model": current.get(CONF_DEVICE_MODEL)
                or current.get(CONF_CONTROLLER_MODEL)
                or "Unknown",
            },
            data_schema=vol.Schema(schema),
        )


def _extract_device_model(device_info: dict[str, Any], fallback: str | None) -> str | None:
    """Return the best model-like value from a Panasonic device info payload."""
    for field in MODEL_FIELD_CANDIDATES:
        value = device_info.get(field)
        if value:
            return str(value)
    return fallback


def _extract_device_model_values(
    device_info: dict[str, Any],
    device_id: str | None = None,
) -> set[str]:
    """Return all model-like values from a Panasonic device info payload."""
    values = set()
    for field in MODEL_FIELD_CANDIDATES:
        value = device_info.get(field)
        if value:
            values.add(str(value))
    if device_id:
        parts = device_id.split("_", 2)
        if len(parts) == 3 and parts[2]:
            values.add(parts[2])
    return values


def _extract_device_id_suffix(device_id: str) -> str | None:
    """Return the model-like suffix from a Panasonic device id."""
    parts = device_id.split("_", 2)
    return parts[2] if len(parts) == 3 and parts[2] else None


def _format_device_label(name: str, model: str | None, device_id: str | None = None) -> str:
    """Format a device option label with model information."""
    if model and device_id:
        return f"{name} - {model} ({device_id})"
    if model:
        return f"{name} - {model}"
    if device_id:
        return f"{name} ({device_id})"
    return name
