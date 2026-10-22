"""Sensor platform for Panasonic Smart China devices (read-only status)."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
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
from .models import PLATFORM_SENSOR
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


# waterCheck 的官方取值含义未公开，这里按"水位档位"保守展示，
# 原始数值同时放在 raw_value 属性里，便于与 App 界面对照修正。
WATER_CHECK_TEXT = {
    0: "缺水",
    1: "水位低",
    2: "水位正常",
    3: "水位高",
}

ONLINE_TEXT = {0: "在线", 1: "离线"}


async def async_setup_entry(hass, entry, async_add_entities):
    """Create status sensors for enabled devices under an account entry."""
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
        if not profile or PLATFORM_SENSOR not in profile.ha_platforms:
            continue
        entity_config = {**entry.data, **device_config, CONF_DEVICE_ID: device_id}
        name = device_config.get(CONF_DEVICE_NAME, device_id)
        for desc in SENSOR_DESCRIPTIONS:
            entities.append(
                PanasonicStatusSensor(
                    hass, entry, entity_config, name, profile, client, account_device_id, desc
                )
            )

    async_add_entities(entities, update_before_add=True)


SENSOR_DESCRIPTIONS = (
    {
        "key": "raHumC",
        "suffix": "室内湿度",
        "kind": "humidity",
        "icon": "mdi:water-percent",
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "waterCheck",
        "suffix": "当前水位",
        "kind": "water",
        "icon": "mdi:water",
    },
    {
        "key": "filPer",
        "suffix": "滤网剩余",
        "kind": "number",
        "icon": "mdi:air-filter",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "offline",
        "suffix": "在线状态",
        "kind": "online",
        "icon": "mdi:wifi",
    },
)


class PanasonicStatusSensor(SensorEntity):
    """加湿器状态传感器（湿度 / 水位 / 滤网 / 在线）。"""

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
            f"panasonic_smart_china_{self._device_id}_{desc['key']}_{desc['kind']}"
        )
        self._attr_icon = desc.get("icon")
        if desc.get("device_class"):
            self._attr_device_class = desc["device_class"]
        if desc.get("unit"):
            self._attr_native_unit_of_measurement = desc["unit"]
        if desc.get("state_class"):
            self._attr_state_class = desc["state_class"]

        self._opt = OptimisticState(
            client,
            get_status_cache(entry.entry_id),
            profile,
            self._usr_id,
            self._device_id,
            self._token,
        )

        self._available = False
        self._state = None
        self._raw = None

    @property
    def available(self):
        return self._available

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"raw_value": self._raw}

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
        raw = _as_int(res.get(self._desc["key"]))
        self._raw = raw
        kind = self._desc["kind"]
        if kind == "water":
            self._state = WATER_CHECK_TEXT.get(raw, f"未知({raw})")
        elif kind == "online":
            self._state = ONLINE_TEXT.get(raw, f"未知({raw})")
        else:
            self._state = raw
