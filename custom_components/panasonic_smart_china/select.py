"""Select platform for Panasonic Smart China 洗衣机/烘干机 程序选择.


由 profile.control_selects 驱动。选择一个程序 -> 通过 WDevSetStatusInfoCommon
下发 program 字段(Read-Modify-Write，保留其它当前设置)。

重要且安全的一点：**选程序只是把程序设到机器上，不会启动运行**。真正开始要按
"开始/暂停"开关。所以即便某个程序的细分参数没完全对齐，机器也不会擅自运转。
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.select import SelectEntity
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
from .models import PLATFORM_SELECT
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
        if not profile or PLATFORM_SELECT not in profile.ha_platforms:
            continue
        if not getattr(profile, "control_selects", ()):
            continue

        coordinator = PanasonicSelectCoordinator(
            hass, client, profile, usr_id, device_id, device_config[CONF_TOKEN]
        )
        await coordinator.async_config_entry_first_refresh()
        model = device_config.get(CONF_DEVICE_MODEL) or device_config.get(CONF_CONTROLLER_MODEL)
        name = device_config.get(CONF_DEVICE_NAME, device_id)
        for desc in profile.control_selects:
            entities.append(
                PanasonicSelect(coordinator, client, profile, usr_id, device_id,
                                device_config[CONF_TOKEN], name, model, desc)
            )
    async_add_entities(entities)


class PanasonicSelectCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, profile, usr_id, device_id, token):
        super().__init__(hass, _LOGGER, name=f"panasonic_sel_{device_id}",
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


class PanasonicSelect(CoordinatorEntity, SelectEntity):
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
        self._val_to_label = dict(desc.options)
        self._label_to_val = {v: k for k, v in desc.options.items()}
        self._attr_options = list(desc.options.values())

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
    def current_option(self):
        data = self.coordinator.data or {}
        val = data.get(self._desc.source_key)
        try:
            val = int(val)
        except (TypeError, ValueError):
            pass
        return self._val_to_label.get(val)

    @property
    def available(self):
        if not super().available:
            return False
        if self._entity_kind in REMOTE_KINDS:
            data = self.coordinator.data or {}
            if str(data.get("remoteStatus", 0)) in ("0", "None"):
                return False
        return True

    async def async_select_option(self, option: str):
        if option not in self._label_to_val:
            _LOGGER.warning("%s: 未知选项 %s", self._attr_name, option)
            return
        status = self.coordinator.data or {}
        if self._entity_kind in REMOTE_KINDS and str(status.get("remoteStatus", 0)) in ("0", "None"):
            _LOGGER.warning("%s：机身未开启远程控制，已忽略。", self._attr_name)
            return
        change = {self._desc.source_key: self._label_to_val[option]}
        params = build_control_payload(self._entity_kind, status, change)
        try:
            await self._client.set_device_status(
                self._profile, self._usr_id, self._device_id, self._token, params
            )
        except PanasonicApiAuthError as err:
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            _LOGGER.error("%s 选择失败: %s", self._attr_name, err)
            return
        await self.coordinator.async_request_refresh()
