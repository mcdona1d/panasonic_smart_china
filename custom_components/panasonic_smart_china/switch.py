"""Switch platform for Panasonic Smart China devices."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo

from .api import PanasonicApiAuthError, PanasonicApiClient, PanasonicApiError
from .const import (
    CONF_CATEGORY,
    CONF_CONTROLLER_MODEL,
    CONF_DEVICE_ID,
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
from .models import PLATFORM_SWITCH
from .profiles import find_profile_for_device_config
from .state_helpers import OptimisticState, get_status_cache

_LOGGER = logging.getLogger(__name__)


def _as_int(value, default=None):
    """Best-effort int conversion for Panasonic status fields."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# 全部为 ADevGetStatusHumi / ADevSetStatusHumi 里的 0/1 布尔字段（已实测可写）。
SWITCH_DESCRIPTIONS = (
    {"key": "childLock", "suffix": "儿童锁", "icon": "mdi:lock"},
    {"key": "uvSterilization", "suffix": "除菌", "icon": "mdi:shield-sun"},
    {"key": "led", "suffix": "灯光", "icon": "mdi:lightbulb"},
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Create the boolean switches of every enabled humidifier."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = runtime.get("client") or PanasonicApiClient(hass, entry.data.get(CONF_SSID))
    account_device_id = runtime.get("account_device_id")
    devices = entry.data.get(CONF_DEVICES, {})

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
        entity_config = {
            **entry.data,
            **device_config,
            CONF_DEVICE_ID: device_id,
        }
        for desc in SWITCH_DESCRIPTIONS:
            entities.append(
                PanasonicStatusSwitch(
                    hass,
                    entry,
                    entity_config,
                    device_config.get(CONF_DEVICE_NAME, device_id),
                    profile,
                    client,
                    account_device_id,
                    desc,
                )
            )

    async_add_entities(entities, update_before_add=True)


class PanasonicStatusSwitch(SwitchEntity):
    """加湿器上的 0/1 开关（儿童锁 / 除菌 / 灯光）。"""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, hass, entry, config, device_name, profile, client, account_device_id, desc):
        self._hass = hass
        self._entry = entry
        self._usr_id = config[CONF_USR_ID]
        self._device_id = config[CONF_DEVICE_ID]
        self._token = config[CONF_TOKEN]
        self._model = config.get(CONF_DEVICE_MODEL) or config.get(CONF_CONTROLLER_MODEL)
        self._api = client
        self._account_device_id = account_device_id
        self._device_name = device_name
        self._profile = profile
        self._desc = desc

        self._attr_name = desc["suffix"]
        self._attr_unique_id = (
            f"panasonic_smart_china_{self._device_id}_{desc['key']}_switch"
        )
        self._attr_icon = desc.get("icon")

        self._opt = OptimisticState(
            client,
            get_status_cache(entry.entry_id),
            profile,
            self._usr_id,
            self._device_id,
            self._token,
        )

        self._available = False
        self._is_on = None
        self._status: dict = {}

    @property
    def available(self):
        return self._available

    @property
    def is_on(self):
        return self._is_on

    @property
    def device_info(self):
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Panasonic",
            model=self._model,
        )
        if self._account_device_id:
            device_info["via_device_id"] = self._account_device_id
        return device_info

    async def async_update(self):
        try:
            res = await self._opt.async_get()
        except PanasonicApiAuthError as err:
            self._available = False
            # 云端会话很短（约 5 分钟）且与手机 App 互斥，这里只标记不可用，
            # 不能因为一次失败就让整个平台装载失败；客户端会自行重新登录。
            _LOGGER.warning("Panasonic session expired for %s: %s", self._device_id, err)
            return
        except PanasonicApiError as err:
            self._available = False
            _LOGGER.debug("Fetch status failed for %s: %s", self._device_id, err)
            return

        self._available = True
        self._status = res
        value = _as_int(res.get(self._desc["key"]))
        self._is_on = None if value is None else value == 1

    async def async_turn_on(self, **kwargs):
        await self._async_set(1)

    async def async_turn_off(self, **kwargs):
        await self._async_set(0)

    async def _async_set(self, value: int):
        try:
            await self._api.set_device_status(
                self._profile,
                self._usr_id,
                self._device_id,
                self._token,
                {self._desc["key"]: value},
            )
        except PanasonicApiAuthError as err:
            self._available = False
            _LOGGER.warning(
                "Panasonic session expired while setting %s: %s", self._device_id, err
            )
            return
        except PanasonicApiError as err:
            _LOGGER.error("Set failed for %s: %s", self._device_id, err)
            return

        # 乐观更新 + 抑制窗口，避免轮询拿回旧值造成开关回跳。
        self._available = True
        self._opt.mark({self._desc["key"]: value})
        merged = dict(self._status)
        merged[self._desc["key"]] = value
        self._status = merged
        self._is_on = value == 1
        self.async_write_ha_state()
