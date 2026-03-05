import logging
import hashlib
from typing import Any, Mapping
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.selector import (
    EntitySelector, EntitySelectorConfig,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode
)

from .const import (
    DOMAIN, CONF_USR_ID, CONF_DEVICE_ID, CONF_TOKEN, 
    CONF_SSID, CONF_SENSOR_ID, CONF_CONTROLLER_MODEL,
    CONF_USERNAME, CONF_FAMILY_ID, CONF_REAL_FAMILY_ID, CONF_DEVICES,
    SUPPORTED_CONTROLLERS,
    find_controllers_for_category, extract_category_from_device_id
)

_LOGGER = logging.getLogger(__name__)

URL_LOGIN = "https://app.psmartcloud.com/App/UsrLogin"
URL_GET_DEV = "https://app.psmartcloud.com/App/UsrGetBindDevInfo"
URL_GET_TOKEN = "https://app.psmartcloud.com/App/UsrGetToken"

class PanasonicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self._username = None
        self._usr_id = None
        self._ssid = None
        self._family_id = None
        self._real_family_id = None
        self._devices = {}
        self._selected_device_ids = []
        self._current_device_index = 0
        self._configured_devices = {}

    async def async_step_user(self, user_input=None):
        """步骤1: 账号登录"""
        errors = {}
        if user_input is not None:
            try:
                self._username = user_input[CONF_USERNAME]
                usr_id, ssid, family_info, devices = await self._authenticate_full_flow(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                
                if not devices:
                    return self.async_abort(reason="no_devices_found")

                self._usr_id = usr_id
                self._ssid = ssid
                self._family_id = family_info['familyId']
                self._real_family_id = family_info['realFamilyId']
                self._devices = devices

                await self.async_set_unique_id(self._usr_id)
                self._abort_if_unique_id_configured()

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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """SSID 过期触发"""
        self._username = entry_data.get(CONF_USERNAME)
        self._usr_id = entry_data.get(CONF_USR_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """重新登录确认框"""
        errors = {}
        if user_input is not None:
            try:
                usr_id, ssid, family_info, devices = await self._authenticate_full_flow(
                    self._username, user_input[CONF_PASSWORD]
                )
                
                reauth_entry = self._get_reauth_entry()
                new_data = dict(reauth_entry.data)
                new_data[CONF_SSID] = ssid
                new_data[CONF_FAMILY_ID] = family_info['familyId']
                new_data[CONF_REAL_FAMILY_ID] = family_info['realFamilyId']
                
                return self.async_update_reload_and_abort(reauth_entry, data=new_data)
            except Exception as e:
                _LOGGER.error("Reauth failed: %s", e)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        """步骤2: 选择要添加的设备 (多选)"""
        errors = {}
        if user_input is not None:
            self._selected_device_ids = user_input["devices"]
            if not self._selected_device_ids:
                errors["base"] = "device_not_supported"
            else:
                return await self.async_step_device_config()

        # 构建设备列表选项
        device_options = []
        for did, info in self._devices.items():
            category = extract_category_from_device_id(did)
            supported = len(find_controllers_for_category(category)) > 0
            label = f"{info.get('deviceName', 'Unknown')} ({did})"
            if supported:
                label = f"✅ 支持: {label}"
            else:
                label = f"❌ 暂不支持: {label}"
            
            device_options.append({"value": did, "label": label})

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required("devices"): SelectSelector(
                    SelectSelectorConfig(
                        options=device_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_device_config(self, user_input=None):
        """步骤3: 为选中的每个设备配置型号 (递归)"""
        if self._current_device_index >= len(self._selected_device_ids):
            # 完成所有选定设备的配置
            return self.async_create_entry(
                title=f"松下账号 ({self._username})",
                data={
                    CONF_USERNAME: self._username,
                    CONF_USR_ID: self._usr_id,
                    CONF_SSID: self._ssid,
                    CONF_FAMILY_ID: self._family_id,
                    CONF_REAL_FAMILY_ID: self._real_family_id,
                    CONF_DEVICES: self._configured_devices
                }
            )

        current_did = self._selected_device_ids[self._current_device_index]
        dev_info = self._devices.get(current_did, {})
        dev_name = dev_info.get("deviceName", "Unknown")

        if user_input is not None:
            token = self._generate_token(current_did)
            self._configured_devices[current_did] = {
                "deviceName": dev_name,
                CONF_CONTROLLER_MODEL: user_input[CONF_CONTROLLER_MODEL],
                CONF_SENSOR_ID: user_input.get(CONF_SENSOR_ID),
                CONF_TOKEN: token
            }
            self._current_device_index += 1
            return await self.async_step_device_config()

        # 查找匹配的控制器
        category = extract_category_from_device_id(current_did)
        matching = find_controllers_for_category(category)
        controller_options = {k: v["name"] for k, v in matching.items()}
        if not controller_options:
             controller_options = {k: v["name"] for k, v in SUPPORTED_CONTROLLERS.items()}
             
        default_controller = list(controller_options.keys())[0] if controller_options else "CZ-RD501DW2"

        return self.async_show_form(
            step_id="device_config",
            title_placeholders={"name": dev_name},
            data_schema=vol.Schema({
                vol.Required(CONF_CONTROLLER_MODEL, default=default_controller): vol.In(controller_options),
                vol.Optional(CONF_SENSOR_ID): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }),
        )

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
                family_info = {
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
                return real_usr_id, ssid, family_info, devices

    def _generate_token(self, device_id):
        """Generate SHA512 token from device_id."""
        try:
            did = device_id.upper()
            parts = did.split('_', 2)
            if len(parts) < 3: return None
            
            mac_part = parts[0]
            category = parts[1]
            suffix = parts[2]
            
            if len(mac_part) < 6: return None
            
            stoken = mac_part[6:] + '_' + category + '_' + mac_part[:6]
            inner = hashlib.sha512(stoken.encode()).hexdigest()
            return hashlib.sha512((inner + '_' + suffix).encode()).hexdigest()
        except Exception:
            return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PanasonicOptionsFlow(config_entry)

class PanasonicOptionsFlow(config_entries.OptionsFlow):
    """配置项管理：修改已添加设备的控制器型号或传感器"""
    
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._devices = config_entry.data.get(CONF_DEVICES, {})
        self._selected_did = None

    async def async_step_init(self, user_input=None):
        """Options flow 主界面"""
        if user_input is not None:
            self._selected_did = user_input[CONF_DEVICE_ID]
            return await self.async_step_edit_device()

        device_options = {did: info.get("deviceName", did) for did, info in self._devices.items()}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(device_options),
            }),
        )

    async def async_step_edit_device(self, user_input=None):
        """配置具体设备的细节"""
        if user_input is not None:
            new_devices = dict(self._devices)
            new_devices[self._selected_did].update({
                CONF_CONTROLLER_MODEL: user_input[CONF_CONTROLLER_MODEL],
                CONF_SENSOR_ID: user_input.get(CONF_SENSOR_ID)
            })
            
            # 更新 Entry Data
            new_data = dict(self.config_entry.data)
            new_data[CONF_DEVICES] = new_devices
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            
            return self.async_create_entry(title="", data={})

        current_config = self._devices[self._selected_did]
        
        category = extract_category_from_device_id(self._selected_did)
        matching = find_controllers_for_category(category)
        controller_options = {k: v["name"] for k, v in matching.items()}
        if not controller_options:
             controller_options = {k: v["name"] for k, v in SUPPORTED_CONTROLLERS.items()}

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema({
                vol.Required(CONF_CONTROLLER_MODEL, default=current_config.get(CONF_CONTROLLER_MODEL)): vol.In(controller_options),
                vol.Optional(CONF_SENSOR_ID, default=current_config.get(CONF_SENSOR_ID)): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }),
        )