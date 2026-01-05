from homeassistant.components.climate.const import (
    HVACMode,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)

DOMAIN = "panasonic_smart_china"

CONF_USR_ID = "usrId"
CONF_DEVICE_ID = "deviceId"
CONF_TOKEN = "token"
CONF_SSID = "SSID"
CONF_SENSOR_ID = "sensor_entity_id"
CONF_CONTROLLER_MODEL = "controller_model"

# 自定义风速常量
FAN_MIN = "Min"    # 最低
FAN_MAX = "Max"    # 最高
FAN_MUTE = "Quiet" # 静音

# === 控制器配置数据库 ===
SUPPORTED_CONTROLLERS = {
    "CZ-RD501DW2": {
        "name": "松下线控器 CZ-RD501DW2",
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
    }
}