"""Humidifier platform for Panasonic Smart China devices.

Field meanings for the 0840 / FE-Z16C humidifier, taken from the official App's
own requests and responses (ADevGetStatusHumi / ADevSetStatusHumi):

    runSta           0 = 关机, 1 = 开机
    runningMode      1 = 轻柔模式, 2 = 智能恒湿, 3 = 手动(档位)模式
    windVoSet        1 = 弱, 2 = 中, 3 = 强, 4 = 急速   (与模式互斥)
    humidSet         目标湿度 = humidSet * 5 + 30 (%), 范围 40~80, 步进 5
                     （实测：humidSet 2~10 对应 40%~80%）
    tH1              与目标湿度无关，属于其它设置，切勿一起写
"""

from __future__ import annotations

import logging

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)
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
from .models import ENTITY_KIND_HUMIDIFIER, PLATFORM_HUMIDIFIER
from .profiles import find_profile_for_device_config
from .state_helpers import OptimisticState, get_status_cache

_LOGGER = logging.getLogger(__name__)

MODE_BY_VALUE = {1: "轻柔模式", 2: "智能恒湿"}
VALUE_BY_MODE = {value: key for key, value in MODE_BY_VALUE.items()}
MANUAL_MODE_VALUE = 3
AVAILABLE_MODES = list(MODE_BY_VALUE.values())

HUMIDITY_MIN = 40
HUMIDITY_MAX = 80
HUMIDITY_STEP = 5
HUMIDITY_OFFSET = 30


def _as_int(value, default=None):
    """Best-effort int conversion for Panasonic status fields."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def async_setup_entry(hass, entry, async_add_entities):
    """Create humidifier entities for enabled devices under an account entry."""
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
        if not profile:
            _LOGGER.error("Device profile not found for %s.", device_id)
            continue

        if PLATFORM_HUMIDIFIER not in profile.ha_platforms:
            continue

        if profile.entity_kind != ENTITY_KIND_HUMIDIFIER:
            _LOGGER.error(
                "Humidifier entity kind %s not implemented for %s.",
                profile.entity_kind,
                device_id,
            )
            continue

        entity_config = {
            **entry.data,
            **device_config,
            CONF_DEVICE_ID: device_id,
        }
        entities.append(
            PanasonicHumidifierEntity(
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


class PanasonicHumidifierEntity(HumidifierEntity):
    """松下加湿器实体 — 开关、模式与目标湿度。"""

    _attr_should_poll = True
    # 当前 HA 版本只有 MODES 这一特性位；目标湿度由 min/max/step 隐式支持。
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = AVAILABLE_MODES
    _attr_min_humidity = HUMIDITY_MIN
    _attr_max_humidity = HUMIDITY_MAX
    _attr_target_humidity_step = HUMIDITY_STEP

    def __init__(self, hass, entry, config, name, profile, client, account_device_id):
        self._hass = hass
        self._entry = entry
        self._usr_id = config[CONF_USR_ID]
        self._device_id = config[CONF_DEVICE_ID]
        self._token = config[CONF_TOKEN]
        self._model = config.get(CONF_DEVICE_MODEL) or config.get(CONF_CONTROLLER_MODEL)
        self._api = client
        self._account_device_id = account_device_id
        self._attr_name = name
        self._attr_unique_id = f"panasonic_smart_china_{self._device_id}_humidifier"
        self._profile = profile
        self._opt = OptimisticState(
            client,
            get_status_cache(entry.entry_id),
            profile,
            self._usr_id,
            self._device_id,
            self._token,
        )

        self._available = False
        self._status: dict = {}

    # --- 属性 ---

    @property
    def available(self):
        return self._available

    @property
    def is_on(self):
        return _as_int(self._status.get("runSta")) == 1

    @property
    def mode(self):
        return MODE_BY_VALUE.get(_as_int(self._status.get("runningMode")))

    @property
    def current_humidity(self):
        return _as_int(self._status.get("raHumC"))

    @property
    def target_humidity(self):
        # 官方 App 实测换算：目标湿度% = humidSet * 5 + 30。
        humid_set = _as_int(self._status.get("humidSet"))
        if humid_set is None:
            return None
        value = humid_set * HUMIDITY_STEP + HUMIDITY_OFFSET
        if value < HUMIDITY_MIN or value > HUMIDITY_MAX:
            return None
        return value

    @property
    def extra_state_attributes(self):
        return {
            "raw_running_mode": self._status.get("runningMode"),
            "raw_wind_vo_set": self._status.get("windVoSet"),
            "raw_humid_set": self._status.get("humidSet"),
            "raw_th1": self._status.get("tH1"),
            "run_sta": self._status.get("runSta"),
        }

    @property
    def device_info(self):
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="Panasonic",
            model=self._model,
        )
        if self._account_device_id:
            device_info["via_device_id"] = self._account_device_id
        return device_info

    # --- 轮询 ---

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

    # --- 命令 ---

    async def async_turn_on(self, **kwargs):
        await self._async_set({"runSta": 1}, optimistic={"runSta": 1})

    async def async_turn_off(self, **kwargs):
        await self._async_set({"runSta": 0}, optimistic={"runSta": 0})

    async def async_set_mode(self, mode: str) -> None:
        value = VALUE_BY_MODE.get(mode)
        if value is None:
            _LOGGER.error("Unsupported humidifier mode %s for %s", mode, self._device_id)
            return
        # 模式与档位互斥：选定模式后设备会把 windVoSet 归零。
        await self._async_set(
            {"runningMode": value},
            optimistic={"runningMode": value, "windVoSet": 0},
        )

    async def async_set_humidity(self, humidity: int) -> None:
        value = int(humidity)
        if (
            value < HUMIDITY_MIN
            or value > HUMIDITY_MAX
            or (value - HUMIDITY_OFFSET) % HUMIDITY_STEP
        ):
            _LOGGER.error(
                "Target humidity %s is not a valid step for %s", humidity, self._device_id
            )
            return
        humid_set = (value - HUMIDITY_OFFSET) // HUMIDITY_STEP
        # 只写 humidSet：tH1 与目标湿度无关，绝不能一起写。
        await self._async_set({"humidSet": humid_set}, optimistic={"humidSet": humid_set})

    async def _async_set(self, params: dict, optimistic: dict | None = None):
        try:
            await self._api.set_device_status(
                self._profile,
                self._usr_id,
                self._device_id,
                self._token,
                params,
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

        # 服务端已接受指令：先乐观更新，并在抑制窗口内压住云端旧值，避免界面回跳。
        self._available = True
        if optimistic:
            self._opt.mark(optimistic)
            merged = dict(self._status)
            merged.update(optimistic)
            self._status = merged
        self.async_write_ha_state()
