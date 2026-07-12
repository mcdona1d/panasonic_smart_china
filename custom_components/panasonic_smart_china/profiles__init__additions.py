"""需要合并进 custom_components/panasonic_smart_china/profiles/__init__.py

只要把新 profile 注册进 SUPPORTED_PROFILES，config_flow 就会自动：
  - 登录后扫描出这些品类设备
  - 允许勾选启用
  - 生成 token、写入配置
sensor.py 也会自动为它们创建传感器。config_flow / __init__.py 无需改动。

抓包里发现的四台设备：
  0600 洗衣机、0610 烘干机、0100 冰箱、0630 自动投放旋钮。
"""

# 1) 顶部 import 区追加：
from .washer_0600 import WASHER_0600_PROFILE
from .dryer_0610 import DRYER_0610_PROFILE
from .fridge_0100 import FRIDGE_0100_PROFILE
from .knob_0630 import KNOB_0630_PROFILE

# 2) SUPPORTED_PROFILES 字典里追加四行：
#
# SUPPORTED_PROFILES = {
#     DUCTED_AC_0900_PROFILE.profile_id: DUCTED_AC_0900_PROFILE,
#     BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE.profile_id: BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE,
#     WASHER_0600_PROFILE.profile_id: WASHER_0600_PROFILE,     # ← 洗衣机
#     DRYER_0610_PROFILE.profile_id: DRYER_0610_PROFILE,       # ← 烘干机
#     FRIDGE_0100_PROFILE.profile_id: FRIDGE_0100_PROFILE,     # ← 冰箱
#     KNOB_0630_PROFILE.profile_id: KNOB_0630_PROFILE,         # ← 投放旋钮
# }
#
# supported_platforms() 会自动收集 "sensor"，__init__.py 会自动加载 sensor.py。
