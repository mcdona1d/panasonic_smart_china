from .profiles import SUPPORTED_PROFILES, find_profiles_for_category
from .profiles.ducted_ac_0900 import FAN_MAX, FAN_MIN, FAN_MUTE

DOMAIN = "panasonic_smart_china"

CONF_USR_ID = "usrId"
CONF_USERNAME = "username"
CONF_DEVICE_ID = "deviceId"
CONF_TOKEN = "token"
CONF_SSID = "SSID"
CONF_SENSOR_ID = "sensor_entity_id"
CONF_CONTROLLER_MODEL = "controller_model"
CONF_FAMILY_ID = "familyId"
CONF_REAL_FAMILY_ID = "realFamilyId"
CONF_DEVICES = "devices"
CONF_DEVICE_NAME = "deviceName"
CONF_DEVICE_MODEL = "device_model"
CONF_CATEGORY = "category"
CONF_ENABLED = "enabled"

# 第一阶段只注册已验证的 0900 风管机 profile。其他品类待后续 profile/adapter
# 扩展层稳定后再接入。
SUPPORTED_CONTROLLERS = {
    "CZ-RD501DW2": SUPPORTED_PROFILES["ducted_ac_0900"],
}


def find_controllers_for_category(category_id):
    """根据设备 ID 中的 category_id 查找匹配的控制器列表"""
    profiles = find_profiles_for_category(category_id)
    return {
        "CZ-RD501DW2": profiles["ducted_ac_0900"]
    } if "ducted_ac_0900" in profiles else {}


def extract_category_from_device_id(device_id):
    """从 deviceId (格式: MAC_CATEGORY_SUFFIX) 中提取 category_id"""
    parts = device_id.split('_', 2)
    if len(parts) >= 2:
        return parts[1]
    return None
