import logging
import async_timeout
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_USR_ID, CONF_DEVICE_ID, CONF_TOKEN, CONF_SSID, 
    CONF_SENSOR_ID, CONF_CONTROLLER_MODEL, 
    SUPPORTED_CONTROLLERS, FAN_MUTE, FAN_MIN, FAN_MAX
)

_LOGGER = logging.getLogger(__name__)

URL_GET = "https://app.psmartcloud.com/App/ACDevGetStatusInfoAW"
URL_SET_AC = "https://app.psmartcloud.com/App/ACDevSetStatusInfoAW"
URL_SET_HEATER = "https://app.psmartcloud.com/App/ADevSetStatusInfoFV54BA1C"

# === 轮询频率 ===
POLLING_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """根据控制器的 device_type 创建对应的实体子类"""
    config = entry.data
    model = config.get(CONF_CONTROLLER_MODEL, "CZ-RD501DW2")
    profile = SUPPORTED_CONTROLLERS.get(model)
    if not profile:
        _LOGGER.error("Controller model %s not found, using default.", model)
        profile = list(SUPPORTED_CONTROLLERS.values())[0]

    dev_type = profile.get("device_type", "AC")

    if dev_type == "Heater":
        entity = PanasonicHeaterEntity(hass, config, entry.title, profile)
    else:
        entity = PanasonicACEntity(hass, config, entry.title, profile)

    async_add_entities([entity])


# ============================================================
# 基类：所有松下设备共享的逻辑
# ============================================================
class PanasonicBaseEntity(ClimateEntity):
    """松下设备基类 — 包含轮询、状态获取、命令发送等通用逻辑"""

    def __init__(self, hass, config, name, profile):
        self._hass = hass
        self._usr_id = config[CONF_USR_ID]
        self._device_id = config[CONF_DEVICE_ID]
        self._token = config[CONF_TOKEN]
        self._ssid = config[CONF_SSID]
        self._attr_name = name
        self._attr_unique_id = f"panasonic_{self._device_id}"

        # 控制器配置
        self._profile = profile
        self._temp_scale = profile.get("temp_scale", 2)
        self._hvac_map = profile.get("hvac_mapping", {})

        # 内部状态
        self._is_on = False
        self._hvac_mode = HVACMode.OFF
        self._target_temperature = 26.0
        self._last_params = {}

        # 定时器句柄
        self._unsub_polling = None

    # --- 轮询管理 ---

    @property
    def should_poll(self):
        return False

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
        headers = self._get_headers()
        payload = {
            "id": 100, "usrId": self._usr_id,
            "deviceId": self._device_id, "token": self._token
        }

        try:
            session = async_get_clientsession(self._hass)
            async with async_timeout.timeout(5):
                response = await session.post(URL_GET, json=payload, headers=headers, ssl=False)
                json_data = await response.json()

                if json_data.get('errorCode') in ['3003', '3004']:
                    _LOGGER.error("SSID expired.")
                    return None

                if 'results' in json_data and 'runStatus' in json_data['results']:
                    res = json_data['results']
                    self._last_params = res

                    if update_internal_state:
                        self._update_local_state(res)

                    return res
        except Exception as e:
            _LOGGER.debug("Fetch status failed: %s", e)
            return None
        return None

    # --- 命令发送 ---

    async def _send_command(self, changes):
        """Read-Modify-Write 核心逻辑 (子类可覆盖 payload 构建)"""

        # 1. Read
        latest_params = await self._fetch_status(update_internal_state=False)

        if latest_params:
            current_params = latest_params.copy()
        else:
            _LOGGER.warning("Could not fetch latest status, using cached params.")
            current_params = self._last_params.copy()

        # 2. Build payload (委托给子类)
        url, params, req_id = self._build_send_payload(changes, current_params)

        # 3. Write
        headers = self._get_headers()
        try:
            session = async_get_clientsession(self._hass)
            async with async_timeout.timeout(10):
                await session.post(url, json={
                    "id": req_id, "usrId": self._usr_id,
                    "deviceId": self._device_id,
                    "token": self._token, "params": params
                }, headers=headers, ssl=False)

                # 4. 更新本地状态 (乐观更新)
                self._update_local_state(params)
                self._last_params.update(params)

                # 5. 强制通知 HA 刷新界面
                self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Set failed: %s", e)

    def _get_headers(self):
        """基础 HTTP Headers，子类可覆盖扩展"""
        return {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X)',
            'xtoken': f'SSID={self._ssid}',
            'DNT': '1',
            'Origin': 'https://app.psmartcloud.com',
            'X-Requested-With': 'XMLHttpRequest'
        }

    # --- 子类必须实现的方法 ---

    def _update_local_state(self, res):
        """解析设备返回的状态数据，更新内部状态变量"""
        raise NotImplementedError

    def _build_send_payload(self, changes, current_params):
        """构建发送的 payload -> (url, params_dict, request_id)"""
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

    def __init__(self, hass, config, name, profile):
        super().__init__(hass, config, name, profile)
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
        self._is_on = (res.get('runStatus') == 1)

        p_mode = res.get('runMode')
        for ha_mode, pm in self._hvac_map.items():
            if pm == p_mode:
                self._hvac_mode = ha_mode
                break

        self._target_temperature = res.get('setTemperature', 52) / self._temp_scale

        p_wind = res.get('windSet')
        p_mute = res.get('muteMode')

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
        p_mode = self._hvac_map.get(hvac_mode, 3)
        return {"runStatus": 1, "runMode": p_mode}

    def _build_on_command(self):
        return {"runStatus": 1}

    def _build_off_command(self):
        return {"runStatus": 0}

    def _build_send_payload(self, changes, current_params):
        """空调：Read-Modify-Write + safe_keys 过滤"""
        current_params.update(changes)

        safe_keys = [
            "runMode", "forceRunning", "runStatus", "remoteForbidMode", "remoteMode",
            "setTemperature", "setHumidity", "windSet", "exchangeWindSet",
            "portraitWindSet", "orientationWindSet", "nanoeG", "nanoe", "ecoMode",
            "muteMode", "filterReset", "powerful", "powerfulMode", "thermoMode", "buzzer",
            "autoRunMode", "unusualPresent", "runForbidden", "inhaleTemperature",
            "outsideTemperature", "insideHumidity", "alarmCode", "nanoeModule", "TDWindModule"
        ]
        params = {k: v for k, v in current_params.items() if k in safe_keys}

        return (URL_SET_AC, params, 200)

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self._send_command({"setTemperature": int(temp * self._temp_scale)})

    async def async_set_fan_mode(self, fan_mode):
        changes = {}
        if fan_mode == FAN_MUTE:
            changes = {"windSet": 10, "muteMode": 1}
        else:
            val = self._fan_map.get(fan_mode, 10)
            changes = {"windSet": val, "muteMode": 0}
        await self._send_command(changes)


# ============================================================
# 浴霸子类 (Heater)
# ============================================================
class PanasonicHeaterEntity(PanasonicBaseEntity):
    """松下浴霸实体 — 模式控制（取暖/换气/凉干燥/热干燥）"""

    @property
    def supported_features(self):
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )

    @property
    def fan_modes(self):
        return []

    @property
    def current_temperature(self):
        """浴霸无外部传感器，返回目标温度"""
        return self._target_temperature

    def _update_local_state(self, res):
        """浴霸使用 runningMode 单字段控制"""
        mode_val = res.get('runningMode', 32)
        self._is_on = (str(mode_val) not in ['32', '0'])

        current_mode_val = int(mode_val) if mode_val is not None else 32
        found_mode = False
        for ha_mode, pm in self._hvac_map.items():
            if pm == current_mode_val:
                self._hvac_mode = ha_mode
                found_mode = True
                break

        if not self._is_on:
            self._hvac_mode = HVACMode.OFF

        raw_temp = res.get('setTemperature') or res.get('warmTempset') or 52
        self._target_temperature = raw_temp / self._temp_scale

    def _build_hvac_command(self, hvac_mode):
        """浴霸通过 runningMode 切换模式"""
        target_val = self._hvac_map.get(hvac_mode, 32)
        return {"runningMode": target_val}

    def _build_on_command(self):
        """默认以换气模式开机"""
        return {"runningMode": 38}

    def _build_off_command(self):
        """runningMode=32 为待机（关机）"""
        return {"runningMode": 32}

    def _build_send_payload(self, changes, current_params):
        """浴霸：固定模板 + 覆盖，不使用 Read-Modify-Write"""
        params = {
            "runningMode": 32,
            "warmTempset": 255, "windDirectionSet": 255, "windKindSet": 255,
            "timeSet": 255, "lightSet": 255,
            "DIYnextRunningMode": 255, "DIYnextWarmTempset": 255,
            "DIYnextwindDirectionSet": 255, "DIYnextwindKindSet": 255,
            "DIYnextTimeSet": 255, "DIYnextStepNo": 2
        }
        params.update(changes)

        # 取暖(37)和换气(38)模式自动设置定时
        mode = params.get("runningMode")
        if mode in [37, 38]:
            params["timeSet"] = 3
        else:
            params["timeSet"] = 255

        return (URL_SET_HEATER, params, 52)

    def _get_headers(self):
        """浴霸需要额外的 Cookie 和 Referer 头"""
        headers = super()._get_headers()
        headers['Cookie'] = f'SSID={self._ssid}'
        headers['Referer'] = (
            f"https://app.psmartcloud.com/ca/cn/0820/RB20VL1/index.html"
            f"?deviceId={self._device_id}&devType=FV-RB20VL1"
        )
        return headers

    async def async_set_temperature(self, **kwargs):
        """浴霸不支持温度设置"""
        pass

    async def async_set_fan_mode(self, fan_mode):
        """浴霸不支持风速设置"""
        pass