"""Select platform for Panasonic Smart China devices (fan gear)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
from .models import PLATFORM_SELECT
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


# 档位（windVoSet）与模式互斥：选择档位时设备会切到手动模式 runningMode=3。
GEAR_BY_VALUE = {1: "弱", 2: "中", 3: "强", 4: "急速"}
VALUE_BY_GEAR = {value: key for key, value in GEAR_BY_VALUE.items()}
MANUAL_MODE_VALUE = 3


async def async_setup_entry(hass, entry, async_add_entities):
    """Create one 档位 select per enabled humidifier."""
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
        if not profile or PLATFORM_SELECT not in profile.ha_platforms:
            continue
        entity_config = {**entry.data, **device_config, CONF_DEVICE_ID: device_id}
        entities.append(
            PanasonicGearSelect(
                hass,
                entry,
                entity_config,
                device_config.get(CONF_DEVICE_NAME, device_id),
                profile,
                client,
                account_device_id,
            )
        )

    async_add_entities(entities, update_before_add=True)


class PanasonicGearSelect(SelectEntity):
    """加湿器档位（弱 / 中 / 强 / 急速）。"""

    _attr_should_poll = True
    _attr_has_entity_name = True
    _attr_name = "档位"
    _attr_icon = "mdi:fan"
    _attr_options = list(GEAR_BY_VALUE.values())

    def __init__(self, hass, entry, config, device_name, profile, client, account_device_id):
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

        self._attr_unique_id = f"panasonic_smart_china_{self._device_id}_gear_select"
        self._opt = OptimisticState(
            client,
            get_status_cache(entry.entry_id),
            profile,
            self._usr_id,
            self._device_id,
            self._token,
        )

        self._available = False
        self._current = None
        self._running_mode = None
        self._raw_gear = None
        self._status: dict = {}

    @property
    def available(self):
        return self._available

    @property
    def current_option(self):
        return self._current

    @property
    def extra_state_attributes(self):
        return {"running_mode": self._running_mode, "raw_wind_vo_set": self._raw_gear}

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
        self._apply(res)

    def _apply(self, res: dict):
        self._running_mode = _as_int(res.get("runningMode"))
        self._raw_gear = _as_int(res.get("windVoSet"))
        # 只有在手动模式下档位才有效；模式生效时设备把档位归零。
        if self._running_mode == MANUAL_MODE_VALUE:
            self._current = GEAR_BY_VALUE.get(self._raw_gear)
        else:
            self._current = None

    async def async_select_option(self, option: str) -> None:
        value = VALUE_BY_GEAR.get(option)
        if value is None:
            _LOGGER.error("Unsupported gear %s for %s", option, self._device_id)
            return
        try:
            await self._api.set_device_status(
                self._profile,
                self._usr_id,
                self._device_id,
                self._token,
                {"runningMode": MANUAL_MODE_VALUE, "windVoSet": value},
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

        # 乐观更新 + 抑制窗口，避免档位显示回跳。
        self._available = True
        written = {"runningMode": MANUAL_MODE_VALUE, "windVoSet": value}
        self._opt.mark(written)
        merged = dict(self._status)
        merged.update(written)
        self._status = merged
        self._apply(merged)
        self.async_write_ha_state()
