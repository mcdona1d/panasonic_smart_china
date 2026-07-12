"""Switch platform for Panasonic Smart China.


覆盖三类开关：
  - 洗衣机/烘干机：电源(powerStatus)、开始/暂停(runingStatus)  -> WDevSetStatusInfoCommon
  - 冰箱：速冻/节能/nanoeX/假期/除味/智能保湿 等布尔开关          -> FDevSetStatusInfoMqtt
  - 投放旋钮：找一找(findStatus)                                  -> WDevSetKnobStatus

payload 由 control_helpers.build_control_payload() 按品类构建（Read-Modify-Write）。

⚠️ 洗衣机/烘干机前提：机身需开启"远程控制"(remoteStatus=1)，否则开关不可用。
⚠️ "开始"带门保护：门开(gateStatus=0)时拒绝启动。
冰箱/旋钮无此限制。
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
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
from .models import PLATFORM_SWITCH
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
        if not profile or PLATFORM_SWITCH not in profile.ha_platforms:
            continue
        if not getattr(profile, "control_switches", ()):
            continue

        coordinator = PanasonicControlCoordinator(
            hass, client, profile, usr_id, device_id, device_config[CONF_TOKEN]
        )
        await coordinator.async_config_entry_first_refresh()
        model = device_config.get(CONF_DEVICE_MODEL) or device_config.get(CONF_CONTROLLER_MODEL)
        name = device_config.get(CONF_DEVICE_NAME, device_id)
        for desc in profile.control_switches:
            entities.append(
                PanasonicControlSwitch(
                    coordinator, client, profile, usr_id, device_id,
                    device_config[CONF_TOKEN], name, model, desc,
                )
            )
    async_add_entities(entities)


class PanasonicControlCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, profile, usr_id, device_id, token):
        super().__init__(hass, _LOGGER, name=f"panasonic_ctrl_{device_id}",
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


class PanasonicControlSwitch(CoordinatorEntity, SwitchEntity):
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

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Panasonic",
            model=self._model,
            via_device=(DOMAIN, self._usr_id),
        )

    def _int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    @property
    def is_on(self):
        data = self.coordinator.data or {}
        return self._int(data.get(self._desc.state_key)) in self._desc.state_on

    @property
    def available(self):
        if not super().available:
            return False
        if self._entity_kind in REMOTE_KINDS:
            data = self.coordinator.data or {}
            if str(data.get("remoteStatus", 0)) in ("0", "None"):
                return False
        return True

    async def async_turn_on(self, **kwargs):
        await self._apply(self._desc.on_change, turning_on=True)

    async def async_turn_off(self, **kwargs):
        await self._apply(self._desc.off_change, turning_on=False)

    async def _apply(self, change: dict, turning_on: bool):
        status = self.coordinator.data or {}

        if self._entity_kind in REMOTE_KINDS:
            if str(status.get("remoteStatus", 0)) in ("0", "None"):
                _LOGGER.warning(
                    "%s：机身未开启远程控制(remoteStatus=0)，已忽略。请在机器上开启远程控制。",
                    self._attr_name,
                )
                return
            if turning_on and self._desc.require_door_closed and str(status.get("gateStatus")) == "0":
                _LOGGER.warning("%s：机门未关闭(gateStatus=0)，拒绝启动。", self._attr_name)
                return

        params = build_control_payload(self._entity_kind, status, change)
        try:
            await self._client.set_device_status(
                self._profile, self._usr_id, self._device_id, self._token, params
            )
        except PanasonicApiAuthError as err:
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            _LOGGER.error("%s 控制失败: %s", self._attr_name, err)
            return
        await self.coordinator.async_request_refresh()
