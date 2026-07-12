"""Number platform for Panasonic Smart China 冰箱温度调节.


由 profile.control_numbers 驱动。冰箱通过 FDevSetStatusInfoMqtt 回传完整状态子集
(Read-Modify-Write)，只改目标温度字段。控制模型取自真实抓包。
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import PanasonicApiAuthError, PanasonicApiClient, PanasonicApiError
from .const import (
    CONF_CATEGORY,
    CONF_CONTROLLER_MODEL,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICES,
    CONF_ENABLED,
    CONF_PROFILE_ID,
    CONF_SSID,
    CONF_TOKEN,
    CONF_USR_ID,
    DOMAIN,
)
from .control_helpers import build_control_payload
from .models import PLATFORM_NUMBER
from .profiles import find_profile_for_device_config

_LOGGER = logging.getLogger(__name__)
POLLING_INTERVAL = timedelta(seconds=30)
REMOTE_KINDS = ("washer", "dryer")


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = runtime.get("client") or PanasonicApiClient(hass, entry.data.get(CONF_SSID))
    devices = entry.data.get(CONF_DEVICES, {})
    usr_id = entry.data[CONF_USR_ID]

    entities = []
    for device_id, device_config in devices.items():
        if not device_config.get(CONF_ENABLED, True):
            continue
        profile = find_profile_for_device_config(
            profile_id=device_config.get(CONF_PROFILE_ID),
            controller_model=device_config.get(CONF_CONTROLLER_MODEL),
            category_id=device_config.get(CONF_CATEGORY),
        )
        if not profile or PLATFORM_NUMBER not in profile.ha_platforms:
            continue
        if not getattr(profile, "control_numbers", ()):
            continue

        coordinator = PanasonicNumberCoordinator(
            hass, client, profile, usr_id, device_id, device_config[CONF_TOKEN]
        )
        await coordinator.async_config_entry_first_refresh()
        model = device_config.get(CONF_DEVICE_MODEL) or device_config.get(CONF_CONTROLLER_MODEL)
        name = device_config.get(CONF_DEVICE_NAME, device_id)
        for desc in profile.control_numbers:
            entities.append(
                PanasonicNumber(coordinator, client, profile, usr_id, device_id,
                                device_config[CONF_TOKEN], name, model, desc)
            )
    async_add_entities(entities)


class PanasonicNumberCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, profile, usr_id, device_id, token):
        super().__init__(hass, _LOGGER, name=f"panasonic_num_{device_id}",
                         update_interval=POLLING_INTERVAL)
        self._client = client
        self._profile = profile
        self._usr_id = usr_id
        self._device_id = device_id
        self._token = token

    async def _async_update_data(self):
        try:
            return await self._client.get_device_status(
                self._profile, self._usr_id, self._device_id, self._token
            )
        except PanasonicApiAuthError as err:
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            raise UpdateFailed(f"更新 {self._device_id} 状态失败: {err}") from err


class PanasonicNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, client, profile, usr_id, device_id, token,
                 device_name, model, desc):
        super().__init__(coordinator)
        self._client = client
        self._profile = profile
        self._entity_kind = profile.entity_kind
        self._usr_id = usr_id
        self._device_id = device_id
        self._token = token
        self._device_name = device_name
        self._model = model
        self._desc = desc
        self._attr_name = f"{device_name} {desc.name}"
        self._attr_unique_id = f"panasonic_smart_china_{device_id}_{desc.key}"
        self._attr_native_min_value = desc.min_value
        self._attr_native_max_value = desc.max_value
        self._attr_native_step = desc.step
        if desc.unit:
            self._attr_native_unit_of_measurement = desc.unit
        if desc.device_class:
            self._attr_device_class = desc.device_class

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Panasonic",
            model=self._model,
            via_device=(DOMAIN, self._usr_id),
        )

    @property
    def available(self):
        if not super().available:
            return False
        if self._entity_kind in REMOTE_KINDS:
            data = self.coordinator.data or {}
            if str(data.get("remoteStatus", 0)) in ("0", "None"):
                return False
        return True

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        val = data.get(self._desc.source_key)
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float):
        status = self.coordinator.data or {}
        if self._entity_kind in REMOTE_KINDS and str(status.get("remoteStatus", 0)) in ("0", "None"):
            _LOGGER.warning("%s：机身未开启远程控制，已忽略。", self._attr_name)
            return
        change = {self._desc.source_key: int(value)}
        params = build_control_payload(self._entity_kind, status, change)
        try:
            await self._client.set_device_status(
                self._profile, self._usr_id, self._device_id, self._token, params
            )
        except PanasonicApiAuthError as err:
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            _LOGGER.error("%s 设置失败: %s", self._attr_name, err)
            return
        await self.coordinator.async_request_refresh()
