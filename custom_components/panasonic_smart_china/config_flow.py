import logging
import hashlib
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN, CONF_USR_ID, CONF_DEVICE_ID, CONF_TOKEN, 
    CONF_SSID, CONF_SENSOR_ID, CONF_CONTROLLER_MODEL,
    SUPPORTED_CONTROLLERS,
    find_controllers_for_category, extract_category_from_device_id
)

_LOGGER = logging.getLogger(__name__)

URL_LOGIN = "https://app.psmartcloud.com/App/UsrLogin"
URL_GET_DEV = "https://app.psmartcloud.com/App/UsrGetBindDevInfo"
URL_GET_TOKEN = "https://app.psmartcloud.com/App/UsrGetToken"

class PanasonicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._login_data = {}
        self._devices = {}
        self._temp_login_info = {}
        # 缓存每个设备的支持信息: {device_id: {supported, category, matching_controllers}}
        self._device_support_map = {}

    async def async_step_user(self, user_input=None):
        """步骤1: 检查缓存 Session 或 登录"""
        errors = {}

        # 1. 检查全局缓存中是否有现成的 Session
        domain_data = self.hass.data.get(DOMAIN, {})
        cached_session = domain_data.get("session")

        if cached_session:
            _LOGGER.info("Found cached session, verifying validity...")
            
            valid_devices = await self._get_devices_with_ssid(
                cached_session[CONF_USR_ID], cached_session[CONF_SSID]
            )
            
            if valid_devices:
                _LOGGER.info("Session valid. Skipping login.")
                self._login_data = {
                    CONF_USR_ID: cached_session[CONF_USR_ID],
                    CONF_SSID: cached_session[CONF_SSID]
                }
                self._devices = valid_devices
                self._analyze_device_support()
                return await self.async_step_device()
            else:
                _LOGGER.warning("Cached session expired.")
                if DOMAIN in self.hass.data:
                    self.hass.data[DOMAIN]["session"] = None

        # 2. 处理用户登录输入
        if user_input is not None:
            try:
                usr_id, ssid, devices = await self._authenticate_full_flow(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                
                if not devices:
                    return self.async_abort(reason="no_devices_found")

                self._login_data = {CONF_USR_ID: usr_id, CONF_SSID: ssid}
                self._devices = devices
                
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN]["session"] = {
                    CONF_USR_ID: usr_id,
                    CONF_SSID: ssid,
                    "devices": devices,
                    "familyId": self._temp_login_info.get('familyId'),
                    "realFamilyId": self._temp_login_info.get('realFamilyId')
                }

                self._analyze_device_support()
                return await self.async_step_device()

            except Exception as e:
                _LOGGER.error("Login failed: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    def _analyze_device_support(self):
        """分析每个设备的支持情况，构建支持映射表"""
        self._device_support_map = {}
        for did in self._devices:
            category = extract_category_from_device_id(did)
            matching = find_controllers_for_category(category) if category else {}
            self._device_support_map[did] = {
                "supported": len(matching) > 0,
                "category": category,
                "matching_controllers": matching
            }

    async def async_step_device(self, user_input=None):
        """步骤2: 选择设备"""
        errors = {}
        
        # 获取已添加的设备，防止重复
        existing_ids = self._async_current_ids()
        
        # 构建可选设备列表（标注支持状态）
        available_devices = {}
        for did, info in self._devices.items():
            if f"panasonic_{did}" not in existing_ids:
                dev_name = info.get('deviceName', 'Unknown')
                support_info = self._device_support_map.get(did, {})
                if support_info.get("supported"):
                    available_devices[did] = f"{dev_name} ({did})"
                else:
                    available_devices[did] = f"⛔ {dev_name} ({did}) [暂不支持]"

        if not available_devices:
            return self.async_abort(reason="all_devices_configured")

        if user_input is not None:
            selected_dev_id = user_input[CONF_DEVICE_ID]
            support_info = self._device_support_map.get(selected_dev_id, {})
            
            # 检查设备是否受支持
            if not support_info.get("supported"):
                errors["base"] = "device_not_supported"
            else:
                dev_info = self._devices.get(selected_dev_id)
                dev_name = dev_info.get("deviceName", "Panasonic Device")
                
                token = self._generate_token(selected_dev_id)
                if not token:
                    errors["base"] = "token_generation_failed"
                else:
                    return self.async_create_entry(
                        title=dev_name,
                        data={
                            CONF_USR_ID: self._login_data[CONF_USR_ID],
                            CONF_SSID: self._login_data[CONF_SSID],
                            CONF_DEVICE_ID: selected_dev_id,
                            CONF_TOKEN: token,
                            CONF_SENSOR_ID: user_input.get(CONF_SENSOR_ID),
                            CONF_CONTROLLER_MODEL: user_input[CONF_CONTROLLER_MODEL], 
                        }
                    )

        # 构建控制器列表
        controller_options = {k: v["name"] for k, v in SUPPORTED_CONTROLLERS.items()}

        # 找出第一个可用设备的默认控制器型号
        default_controller = "CZ-RD501DW2"
        for did, support_info in self._device_support_map.items():
            if f"panasonic_{did}" not in existing_ids and support_info.get("supported"):
                matching = support_info.get("matching_controllers", {})
                if matching:
                    default_controller = list(matching.keys())[0]
                    break

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(available_devices),
                vol.Required(CONF_CONTROLLER_MODEL, default=default_controller): vol.In(controller_options),
                vol.Optional(CONF_SENSOR_ID): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }),
            errors=errors,
        )

    async def _get_devices_with_ssid(self, usr_id, ssid):
        """仅使用 SSID 尝试获取设备列表 (用于验证 Session)"""
        headers = {'User-Agent': 'SmartApp', 'Content-Type': 'application/json', 'Cookie': f"SSID={ssid}"}
        
        domain_data = self.hass.data.get(DOMAIN, {})
        session_cache = domain_data.get("session")
        
        if not session_cache or 'familyId' not in session_cache:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(URL_GET_DEV, json={
                    "id": 3, "uiVersion": 4.0,
                    "params": {
                        "realFamilyId": session_cache['realFamilyId'], 
                        "familyId": session_cache['familyId'], 
                        "usrId": usr_id
                    }
                }, headers=headers, ssl=False) as resp:
                    if resp.status != 200: return None
                    dev_res = await resp.json()
                    if 'results' not in dev_res: return None
                    
                    devices = {}
                    for dev in dev_res['results']['devList']:
                        devices[dev['deviceId']] = dev['params']
                    return devices
        except:
            return None

    async def _authenticate_full_flow(self, username, password):
        """完整的登录流程"""
        headers = {'User-Agent': 'SmartApp', 'Content-Type': 'application/json'}
        async with aiohttp.ClientSession() as session:
            # 1. GetToken
            async with session.post(URL_GET_TOKEN, json={
                "id": 1, "uiVersion": 4.0, "params": {"usrId": username}
            }, headers=headers, ssl=False) as resp:
                data = await resp.json()
                if 'results' not in data: raise Exception("GetToken Failed")
                token_start = data['results']['token']
            
            # 2. Calc Password
            pwd_md5 = hashlib.md5(password.encode()).hexdigest().upper()
            inter_md5 = hashlib.md5((pwd_md5 + username).encode()).hexdigest().upper()
            final_token = hashlib.md5((inter_md5 + token_start).encode()).hexdigest().upper()
            
            # 3. Login
            async with session.post(URL_LOGIN, json={
                "id": 2, "uiVersion": 4.0, 
                "params": {"telId": "00:00:00:00:00:00", "checkFailCount": 0, "usrId": username, "pwd": final_token}
            }, headers=headers, ssl=False) as resp:
                login_res = await resp.json()
                if "results" not in login_res: raise Exception("Login Failed")
                
                res = login_res['results']
                real_usr_id = res['usrId']
                ssid = res['ssId']
                
                self._temp_login_info = {
                    'realFamilyId': res['realFamilyId'],
                    'familyId': res['familyId']
                }

            # 4. Get Devices
            headers['Cookie'] = f"SSID={ssid}"
            async with session.post(URL_GET_DEV, json={
                "id": 3, "uiVersion": 4.0,
                "params": {"realFamilyId": res['realFamilyId'], "familyId": res['familyId'], "usrId": real_usr_id}
            }, headers=headers, ssl=False) as resp:
                dev_res = await resp.json()
                devices = {}
                if 'results' in dev_res and 'devList' in dev_res['results']:
                    for dev in dev_res['results']['devList']:
                        devices[dev['deviceId']] = dev['params']
                return real_usr_id, ssid, devices

    def _generate_token(self, device_id):
        """
        Generate SHA512 token from device_id.
        
        deviceId format: MAC_CATEGORY_SUFFIX (e.g., A1B2C3D4E5F6_0900_1234)
        使用 split('_', 2) 安全分割，兼容后缀中可能包含下划线的设备 ID
        """
        try:
            did = device_id.upper()
            
            parts = did.split('_', 2)
            if len(parts) < 3:
                _LOGGER.error("Invalid deviceId format: %s (expected MAC_CATEGORY_SUFFIX)", device_id)
                return None
            
            mac_part = parts[0]
            category = parts[1]
            suffix = parts[2]
            
            if len(mac_part) < 6:
                _LOGGER.error("Invalid MAC part in deviceId: %s", device_id)
                return None
            
            stoken = mac_part[6:] + '_' + category + '_' + mac_part[:6]
            inner = hashlib.sha512(stoken.encode()).hexdigest()
            return hashlib.sha512((inner + '_' + suffix).encode()).hexdigest()
        except Exception as e:
            _LOGGER.error("Token generation failed for deviceId %s: %s", device_id, e)
            return None