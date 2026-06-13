import logging
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature, 
    HVACMode, 
    FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH,
)
from homeassistant.const import (
    ATTR_TEMPERATURE, 
    STATE_UNAVAILABLE, 
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.device_registry import DeviceInfo

from .api import PanasonicApiAuthError, PanasonicApiClient, PanasonicApiError
from .const import (
    CONF_CONTROLLER_MODEL,
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICES,
    CONF_ENABLED,
    CONF_SENSOR_ID,
    CONF_SSID,
    CONF_TOKEN,
    CONF_USR_ID,
    DOMAIN,
    SUPPORTED_CONTROLLERS,
    FAN_MUTE,
)

_LOGGER = logging.getLogger(__name__)

# === 轮询频率 ===
POLLING_INTERVAL = timedelta(seconds=15)


def _as_int(value, default=None):
    """Best-effort int conversion for Panasonic status fields."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def async_setup_entry(hass, entry, async_add_entities):
    """Create climate entities for all enabled devices under an account entry."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = runtime.get("client") or PanasonicApiClient(hass, entry.data.get(CONF_SSID))
    devices = entry.data.get(CONF_DEVICES, {})

    entities = []
    for device_id, device_config in devices.items():
        if not device_config.get(CONF_ENABLED, True):
            continue

        model = device_config.get(CONF_CONTROLLER_MODEL, "CZ-RD501DW2")
        profile = SUPPORTED_CONTROLLERS.get(model)
        if not profile:
            _LOGGER.error("Controller model %s not found for %s.", model, device_id)
            continue

        if profile.get("device_type", "AC") != "AC":
            _LOGGER.error("Unsupported device type for controller model %s", model)
            continue

        entity_config = {
            **entry.data,
            **device_config,
            CONF_DEVICE_ID: device_id,
        }
        entities.append(
            PanasonicACEntity(
                hass,
                entry,
                entity_config,
                device_config.get(CONF_DEVICE_NAME, device_id),
                profile,
                client,
            )
        )

    async_add_entities(entities, update_before_add=True)


# ============================================================
# 基类：所有松下设备共享的逻辑
# ============================================================
class PanasonicBaseEntity(ClimateEntity):
    """松下设备基类 — 包含轮询、状态获取、命令发送等通用逻辑"""

    def __init__(self, hass, entry, config, name, profile, client):
        self._hass = hass
        self._entry = entry
        self._usr_id = config[CONF_USR_ID]
        self._device_id = config[CONF_DEVICE_ID]
        self._token = config[CONF_TOKEN]
        self._model = config.get(CONF_DEVICE_MODEL) or config.get(CONF_CONTROLLER_MODEL)
        self._api = client
        self._attr_name = name
        self._attr_unique_id = f"panasonic_smart_china_{self._device_id}_climate"

        # 控制器配置
        self._profile = profile
        self._temp_scale = profile.get("temp_scale", 2)
        self._hvac_map = profile.get("hvac_mapping", {})
        self._default_hvac_mode = profile.get("default_hvac_mode", HVACMode.COOL)

        # 内部状态
        self._available = False
        self._is_on = False
        self._hvac_mode = self._default_hvac_mode
        self._target_temperature = 26.0
        self._last_active_target_temperature = self._target_temperature
        self._last_params = {}

        # 定时器句柄
        self._unsub_polling = None

    # --- 轮询管理 ---

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._available

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="Panasonic",
            model=self._model,
            via_device=(DOMAIN, self._usr_id),
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsub_polling = async_track_time_interval(
            self._hass, self._async_update_interval_wrapper, POLLING_INTERVAL
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_polling:
            self._unsub_polling()
            self._unsub_polling = None
        await super().async_will_remove_from_hass()

    async def _async_update_interval_wrapper(self, now):
        await self.async_update()
        self.async_write_ha_state()

    # --- 通用属性 ---

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        return 16.0

    @property
    def max_temp(self):
        return 30.0

    @property
    def target_temperature_step(self):
        return 1.0

    @property
    def hvac_modes(self):
        modes = [HVACMode.OFF]
        modes.extend(k for k in self._hvac_map.keys() if k != HVACMode.OFF)
        return modes

    @property
    def hvac_mode(self):
        if not self._is_on:
            return HVACMode.OFF
        return self._hvac_mode

    @property
    def target_temperature(self):
        return self._target_temperature

    # --- 状态获取 ---

    async def async_update(self):
        await self._fetch_status(update_internal_state=True)

    async def _fetch_status(self, update_internal_state=True):
        """通用方法：获取设备当前最新状态"""
        try:
            res = await self._api.get_ac_status(self._usr_id, self._device_id, self._token)
            self._last_params = res.copy()
            if update_internal_state:
                self._available = True
                self._update_local_state(res)
            return res
        except PanasonicApiAuthError as err:
            self._available = False
            _LOGGER.error("Panasonic session expired for %s: %s", self._device_id, err)
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            if update_internal_state:
                self._available = False
            _LOGGER.debug("Fetch status failed for %s: %s", self._device_id, err)
            return None

    # --- 命令发送 ---

    async def _send_command(self, changes):
        """Read-Modify-Write 核心逻辑 (子类可覆盖 payload 构建)"""

        # 1. Read
        latest_params = await self._fetch_status(update_internal_state=False)

        if latest_params:
            current_params = latest_params.copy()
        else:
            _LOGGER.warning(
                "Could not fetch latest status for %s; aborting command %s.",
                self._device_id,
                changes,
            )
            return

        # 2. Build payload (委托给子类)
        params = self._build_send_payload(changes, current_params)

        # 3. Write
        try:
            await self._api.set_ac_status(self._usr_id, self._device_id, self._token, params)
        except PanasonicApiAuthError as err:
            self._available = False
            _LOGGER.error("Panasonic session expired while setting %s: %s", self._device_id, err)
            raise ConfigEntryAuthFailed("Panasonic Smart China session expired") from err
        except PanasonicApiError as err:
            _LOGGER.error("Set failed for %s: %s", self._device_id, err)
            return

        # 4. 仅在服务端接受指令后更新本地状态
        self._available = True
        self._last_params.update(params)
        self._update_local_state(self._last_params)

        # 5. 强制通知 HA 刷新界面
        self.async_write_ha_state()

    # --- 子类必须实现的方法 ---

    def _update_local_state(self, res):
        """解析设备返回的状态数据，更新内部状态变量"""
        raise NotImplementedError

    def _build_send_payload(self, changes, current_params):
        """构建发送的 payload -> params_dict"""
        raise NotImplementedError

    def _build_hvac_command(self, hvac_mode):
        """构建模式切换的命令参数 -> dict"""
        raise NotImplementedError

    def _build_on_command(self):
        """构建开机命令参数 -> dict"""
        raise NotImplementedError

    def _build_off_command(self):
        """构建关机命令参数 -> dict"""
        raise NotImplementedError

    # --- 通用动作 ---

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self._send_command(self._build_off_command())
        else:
            await self._send_command(self._build_hvac_command(hvac_mode))

    async def async_turn_on(self):
        await self._send_command(self._build_on_command())

    async def async_turn_off(self):
        await self._send_command(self._build_off_command())


# ============================================================
# 空调子类 (AC)
# ============================================================
class PanasonicACEntity(PanasonicBaseEntity):
    """松下空调实体 — 支持温度设置、风速控制"""

    def __init__(self, hass, entry, config, name, profile, client):
        super().__init__(hass, entry, config, name, profile, client)
        self._sensor_id = config.get(CONF_SENSOR_ID)
        self._fan_map = profile.get("fan_mapping", {})
        self._fan_overrides = profile.get("fan_payload_overrides", {})
        self._fan_mode = FAN_AUTO

    @property
    def supported_features(self):
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.FAN_MODE
        )

    @property
    def fan_modes(self):
        modes = list(self._fan_map.keys())
        for mode in self._fan_overrides.keys():
            if mode not in modes:
                modes.append(mode)
        return modes

    @property
    def fan_mode(self):
        return self._fan_mode

    @property
    def current_temperature(self):
        if not self._sensor_id:
            return None
        state = self._hass.states.get(self._sensor_id)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                return float(state.state)
            except ValueError:
                pass
        return None

    def _update_local_state(self, res):
        self._is_on = (_as_int(res.get('runStatus')) == 1)

        p_mode = _as_int(res.get('runMode'))
        for ha_mode, pm in self._hvac_map.items():
            if pm == p_mode:
                self._hvac_mode = ha_mode
                break

        raw_temp = _as_int(res.get('setTemperature'))
        if raw_temp is not None:
            target = raw_temp / self._temp_scale
            if self.min_temp <= target <= self.max_temp:
                self._target_temperature = target
                if self._is_on:
                    self._last_active_target_temperature = target

        p_wind = _as_int(res.get('windSet'))
        p_mute = _as_int(res.get('muteMode'))

        if p_wind == 10 and p_mute == 1:
            self._fan_mode = FAN_MUTE
        else:
            found_normal = False
            for name, val in self._fan_map.items():
                if val == p_wind:
                    self._fan_mode = name
                    found_normal = True
                    break
            if not found_normal:
                self._fan_mode = FAN_AUTO

    def _build_hvac_command(self, hvac_mode):
        p_mode = self._hvac_map.get(hvac_mode, self._hvac_map[self._default_hvac_mode])
        return {
            "runStatus": 1,
            "runMode": p_mode,
            "setTemperature": int(self._last_active_target_temperature * self._temp_scale),
        }

    def _build_on_command(self):
        hvac_mode = self._hvac_mode if self._hvac_mode != HVACMode.OFF else self._default_hvac_mode
        return {
            "runStatus": 1,
            "runMode": self._hvac_map.get(hvac_mode, self._hvac_map[self._default_hvac_mode]),
            "setTemperature": int(self._last_active_target_temperature * self._temp_scale),
        }

    def _build_off_command(self):
        return {"runStatus": 0}

    def _build_send_payload(self, changes, current_params):
        """空调：Read-Modify-Write + safe_keys 过滤"""
        current_params.update(changes)

        safe_keys = self._profile.get("safe_status_keys", set())
        params = {k: v for k, v in current_params.items() if k in safe_keys}

        return params

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        if not self._is_on:
            _LOGGER.info(
                "Ignoring target temperature %.1f for %s while device is off.",
                temp,
                self._device_id,
            )
            return
        await self._send_command({"setTemperature": int(temp * self._temp_scale)})

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode == FAN_MUTE:
            changes = self._fan_overrides.get(FAN_MUTE, {"windSet": 10, "muteMode": 1})
        else:
            val = self._fan_map.get(fan_mode)
            if val is None:
                _LOGGER.warning("Unsupported fan mode %s for %s", fan_mode, self._device_id)
                return
            changes = {"windSet": val, "muteMode": 0}
        await self._send_command(changes)
