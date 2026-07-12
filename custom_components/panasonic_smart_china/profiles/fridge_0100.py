"""冰箱 profile（已按你的抓包数据填好）。

品类代号 0100   (deviceId 形如 <MAC>_0100_Fridge-55)
状态接口: FDevGetStatusInfo  (返回 111 个字段)
温度字段直接是摄氏度整数(如 4, -20, -3)，无需 scale。
只读传感器。若日后想控制(切模式/调温)，见指南 §6，参考 climate.py 的 Read-Modify-Write。

温区约定(据抓包值推断)：
  PC = 冷藏室(Provision, +4℃)   FC = 冷冻室(Freezer, -20℃)   SCB1 = 变温室(-3℃)
"""
from __future__ import annotations

from ..models import (
    ENTITY_KIND_FRIDGE,
    PLATFORM_NUMBER,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PROTOCOL_GENERIC_STATUS,
    PanasonicEndpoint,
    PanasonicNumberDescription,
    PanasonicProfile,
    PanasonicSensorDescription,
    PanasonicSwitchDescription,
)

ONOFF = {0: "关", 1: "开"}

FRIDGE_0100_PROFILE = PanasonicProfile(
    profile_id="fridge_0100",
    controller_model="松下冰箱-0100",
    name="松下冰箱 (0100)",
    category_ids=frozenset({"0100"}),
    ha_platforms=(PLATFORM_SENSOR, PLATFORM_SWITCH, PLATFORM_NUMBER),
    entity_kind=ENTITY_KIND_FRIDGE,
    protocol=PROTOCOL_GENERIC_STATUS,
    status_endpoint=PanasonicEndpoint(
        path="FDevGetStatusInfo",
        request_id=100,
        require_results=True,
        required_result_keys=frozenset({"FCTempCur"}),
    ),
    set_endpoint=PanasonicEndpoint(
        path="FDevSetStatusInfoMqtt",
        request_id=200,
        require_results=False,
    ),
    sensor_descriptions=(
        PanasonicSensorDescription(
            key="fridge_temp_cur", source_key="PCTempCur",
            name="冷藏室温度", unit="°C", device_class="temperature"),
        PanasonicSensorDescription(
            key="fridge_temp_set", source_key="PCTempSet",
            name="冷藏室设定", unit="°C", device_class="temperature"),
        PanasonicSensorDescription(
            key="freezer_temp_cur", source_key="FCTempCur",
            name="冷冻室温度", unit="°C", device_class="temperature"),
        PanasonicSensorDescription(
            key="freezer_temp_set", source_key="FCTempSet",
            name="冷冻室设定", unit="°C", device_class="temperature"),
        PanasonicSensorDescription(
            key="switch_temp_set", source_key="SCB1TempSet",
            name="变温室设定", unit="°C", device_class="temperature"),
        PanasonicSensorDescription(
            key="quick_freeze", source_key="quickFreeze",
            name="速冻", value_map=ONOFF),
        PanasonicSensorDescription(
            key="quick_cooling", source_key="quickCooling",
            name="速冷", value_map=ONOFF),
        PanasonicSensorDescription(
            key="eco_mode", source_key="ecoMode",
            name="节能模式", value_map=ONOFF),
        PanasonicSensorDescription(
            key="vacation", source_key="vacation",
            name="假期模式", value_map=ONOFF),
        PanasonicSensorDescription(
            key="nanoe", source_key="nanoe",
            name="nanoeX", value_map=ONOFF),
        PanasonicSensorDescription(
            key="smart_humi", source_key="smartHumi",
            name="智能保湿", value_map=ONOFF),
        PanasonicSensorDescription(
            key="gate_alarm", source_key="gateAlarm",
            name="门未关报警", value_map={0: "正常", 1: "报警"}),
        PanasonicSensorDescription(
            key="alarm_code", source_key="alarmCode",
            name="故障代码"),
    ),
    control_numbers=(
        PanasonicNumberDescription(
            key="fridge_temp", source_key="PCTempSet", name="冷藏室设定温度",
            min_value=1, max_value=7, step=1, unit="°C", device_class="temperature"),
        PanasonicNumberDescription(
            key="freezer_temp", source_key="FCTempSet", name="冷冻室设定温度",
            min_value=-24, max_value=-15, step=1, unit="°C", device_class="temperature"),
        PanasonicNumberDescription(
            key="switch_temp", source_key="SCB1TempSet", name="变温室设定温度",
            min_value=-7, max_value=5, step=1, unit="°C", device_class="temperature"),
    ),
    control_switches=(
        PanasonicSwitchDescription(
            key="quick_icing", name="快速制冰", state_key="quickicing",
            on_change={"quickicing": 1}, off_change={"quickicing": 0}),
        PanasonicSwitchDescription(
            key="auto_icing", name="自动制冰", state_key="autoIcing",
            on_change={"autoIcing": 1}, off_change={"autoIcing": 0}),
        PanasonicSwitchDescription(
            key="icing_stop", name="停止制冰", state_key="icingStop",
            on_change={"icingStop": 1}, off_change={"icingStop": 0}),
        PanasonicSwitchDescription(
            key="icing_deice", name="制冰化霜", state_key="icingDeice",
            on_change={"icingDeice": 1}, off_change={"icingDeice": 0}),
        PanasonicSwitchDescription(
            key="dry_store", name="变温室干燥储存", state_key="SCS1DryStore",
            on_change={"SCS1DryStore": 1}, off_change={"SCS1DryStore": 0}),
        PanasonicSwitchDescription(
            key="pc_micro_freeze", name="冷藏微冻", state_key="PCMicroFreeze",
            on_change={"PCMicroFreeze": 1}, off_change={"PCMicroFreeze": 0}),
        PanasonicSwitchDescription(
            key="fresh_frozen", name="微冻鲜存", state_key="freshFrozen",
            on_change={"freshFrozen": 1}, off_change={"freshFrozen": 0}),
        PanasonicSwitchDescription(
            key="preservation", name="保鲜", state_key="preservation",
            on_change={"preservation": 1}, off_change={"preservation": 0}),
        PanasonicSwitchDescription(
            key="silver", name="银离子除菌", state_key="silver",
            on_change={"silver": 1}, off_change={"silver": 0}),
        PanasonicSwitchDescription(
            key="quick_freeze", name="速冻", state_key="quickFreeze",
            on_change={"quickFreeze": 1}, off_change={"quickFreeze": 0}),
        PanasonicSwitchDescription(
            key="nanoe", name="nanoeX", state_key="nanoe",
            on_change={"nanoe": 1}, off_change={"nanoe": 0}),
        PanasonicSwitchDescription(
            key="erase_odor", name="除味", state_key="eraseOdor",
            on_change={"eraseOdor": 1}, off_change={"eraseOdor": 0}),
        PanasonicSwitchDescription(
            key="smart_humi", name="智能保湿", state_key="smartHumi",
            on_change={"smartHumi": 1}, off_change={"smartHumi": 0}),
        PanasonicSwitchDescription(
            key="water_fresh", name="水润保湿", state_key="waterFresh",
            on_change={"waterFresh": 1}, off_change={"waterFresh": 0}),
        PanasonicSwitchDescription(
            key="eco_mode", name="节能模式", state_key="ecoMode",
            on_change={"ecoMode": 1}, off_change={"ecoMode": 0}),
        PanasonicSwitchDescription(
            key="econavi", name="ECONAVI 节能", state_key="ecoNaviSet",
            on_change={"ecoNaviSet": 1}, off_change={"ecoNaviSet": 0}),
        PanasonicSwitchDescription(
            key="vacation", name="假期模式", state_key="vacation",
            on_change={"vacation": 1}, off_change={"vacation": 0}),
        PanasonicSwitchDescription(
            key="mood_lighting", name="情景灯光", state_key="moodLighting",
            on_change={"moodLighting": 1}, off_change={"moodLighting": 0}),
    ),
)
