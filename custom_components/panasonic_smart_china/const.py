from homeassistant.components.climate.const import (
    HVACMode,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)

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

# 自定义风速常量
FAN_MIN = "Min"    # 最低
FAN_MAX = "Max"    # 最高
FAN_MUTE = "Quiet" # 静音

# === 控制器配置数据库 ===
SUPPORTED_CONTROLLERS = {
    "CZ-RD501DW2": {
        "name": "松下风管机线控器 (CZ-RD501DW2)",
        "device_type": "AC",
        "category_ids": ["0900"],  # 空调类别码
        "temp_scale": 2,
        "hvac_mapping": {
            HVACMode.COOL: 3,
            HVACMode.HEAT: 4,
            HVACMode.DRY: 2,
            HVACMode.AUTO: 0,
        },
        # 基础风速映射 (windSet 数值)
        "fan_mapping": {
            FAN_AUTO: 10,   # 自动
            FAN_MIN: 3,     # 最低
            FAN_LOW: 4,     # 低
            FAN_MEDIUM: 5,  # 中
            FAN_HIGH: 6,    # 高
            FAN_MAX: 7,     # 最高
        },
        # 特殊模式覆盖 (仅定义静音即可，其他走通用逻辑)
        "fan_payload_overrides": {
            FAN_MUTE: {"windSet": 10, "muteMode": 1}
        }
    },
    "FV-RB20VL1": {
        "name": "松下浴霸 (FV-RB20VL1)",
        "device_type": "Heater",
        "category_ids": ["0820"],  # 浴霸类别码
        "temp_scale": 1,
        "hvac_mapping": {
            HVACMode.OFF: 32,       # 待机
            HVACMode.HEAT: 37,      # 取暖
            HVACMode.FAN_ONLY: 38,  # 换气
            HVACMode.COOL: 40,      # 凉干燥
            HVACMode.DRY: 42,       # 热干燥
        },
        "fan_mapping": {},
        "fan_payload_overrides": {}
    }
}


def find_controllers_for_category(category_id):
    """根据设备 ID 中的 category_id 查找匹配的控制器列表"""
    matches = {}
    for key, profile in SUPPORTED_CONTROLLERS.items():
        if category_id in profile.get("category_ids", []):
            matches[key] = profile
    return matches


def extract_category_from_device_id(device_id):
    """从 deviceId (格式: MAC_CATEGORY_SUFFIX) 中提取 category_id"""
    parts = device_id.split('_', 2)
    if len(parts) >= 2:
        return parts[1]
    return None