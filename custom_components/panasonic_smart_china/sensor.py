"""Sensor platform for Panasonic Smart China (冰箱 / 洗衣机 等只读设备).

这是一个新的 HA 平台模块，架构里原本只有 climate.py，没有 sensor.py。
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
from .models import PLATFORM_SENSOR
from .profiles import find_profile_for_device_config

_LOGGER = logging.getLogger(__name__)

POLLING_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    """为账号下所有启用的、且带 sensor_descriptions 的设备创建传感器。"""
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
        if not profile or PLATFORM_SENSOR not in profile.ha_platforms:
            continue
        if not getattr(profile, "sensor_descriptions", ()):
            continue

        coordinator = PanasonicDeviceCoordinator(
            hass, client, profile, usr_id, device_id, device_config[CONF_TOKEN]
        )
        await coordinator.async_config_entry_first_refresh()

        model = device_config.get(CONF_DEVICE_MODEL) or device_config.get(
            CONF_CONTROLLER_MODEL
        )
        name = device_config.get(CONF_DEVICE_NAME, device_id)
        for desc in profile.sensor_descriptions:
            entities.append(
                PanasonicSensor(coordinator, device_id, usr_id, name, model, desc)
            )

    async_add_entities(entities)


class PanasonicDeviceCoordinator(DataUpdateCoordinator):
    """每个设备一个协调器，所有传感器共享一次状态拉取。"""
    def __init__(self, hass, client, profile, usr_id, device_id, token):
        super().__init__(
            hass,
            _LOGGER,
            name=f"panasonic_smart_china_{device_id}",
            update_interval=POLLING_INTERVAL,
        )
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


class PanasonicSensor(CoordinatorEntity, SensorEntity):
    """由 PanasonicSensorDescription 驱动的通用传感器。"""
    def __init__(self, coordinator, device_id, usr_id, device_name, model, desc):
        super().__init__(coordinator)
        self._device_id = device_id
        self._usr_id = usr_id
        self._device_name = device_name
        self._model = model
        self._desc = desc

        self._attr_name = f"{device_name} {desc.name}"
        self._attr_unique_id = f"panasonic_smart_china_{device_id}_{desc.key}"
        if desc.device_class:
            self._attr_device_class = desc.device_class
        if desc.unit:
            self._attr_native_unit_of_measurement = desc.unit
        if desc.state_class:
            self._attr_state_class = desc.state_class
        elif desc.unit:
            self._attr_state_class = SensorStateClass.MEASUREMENT

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
    def native_value(self):
        data = self.coordinator.data or {}
        raw = data.get(self._desc.source_key)
        if raw is None:
            return None

        if self._desc.value_map:
            return self._desc.value_map.get(_maybe_int(raw), raw)

        if self._desc.scale:
            try:
                return round(float(raw) / self._desc.scale, 2)
            except (TypeError, ValueError):
                return None

        return raw


def _maybe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value
