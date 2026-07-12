"""自动投放旋钮配件 profile（已按你的抓包数据填好）。

品类代号 0630   子类 45   (deviceId 形如 <MAC>_0630_03-03)
状态接口: WDevGetKnobStatus（返回 7 个字段）
这是洗衣机的自动投放旋钮/称重配件，有独立电池。
本 profile 只做只读传感器；App 里的"找一找"(findStatus=1 蜂鸣)是写操作，
若想做成按钮实体可另加 button 平台，参考 climate.py 的写请求方式，
set 接口为 WDevSetKnobStatus，body params={"findStatus":1}。
"""
from __future__ import annotations

from ..models import (
    ENTITY_KIND_KNOB,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PROTOCOL_GENERIC_STATUS,
    PanasonicEndpoint,
    PanasonicProfile,
    PanasonicSensorDescription,
    PanasonicSwitchDescription,
)

KNOB_0630_PROFILE = PanasonicProfile(
    profile_id="knob_0630",
    controller_model="松下投放旋钮-0630",
    name="松下投放旋钮 (0630)",
    category_ids=frozenset({"0630"}),
    ha_platforms=(PLATFORM_SENSOR, PLATFORM_SWITCH),
    entity_kind=ENTITY_KIND_KNOB,
    protocol=PROTOCOL_GENERIC_STATUS,
    status_endpoint=PanasonicEndpoint(
        path="WDevGetKnobStatus",
        request_id=100,
        require_results=True,
        required_result_keys=frozenset({"electricity"}),
    ),
    set_endpoint=PanasonicEndpoint(
        path="WDevSetKnobStatus",
        request_id=200,
        require_results=False,
    ),
    sensor_descriptions=(
        PanasonicSensorDescription(
            key="battery", source_key="electricity",
            name="电量", unit="%", device_class="battery"),
        PanasonicSensorDescription(
            key="charge_status", source_key="chargeStatus",
            name="充电状态", value_map={0: "未充电", 1: "充电中"}),
        PanasonicSensorDescription(
            key="adsorbed", source_key="adsorbedStatus",
            name="吸附状态", value_map={0: "未吸附", 1: "已吸附"}),
        PanasonicSensorDescription(
            key="online", source_key="knobOfflineStatus",
            name="在线状态", value_map={0: "在线", 1: "离线"}),
    ),
    control_switches=(
        PanasonicSwitchDescription(
            key="find", name="找一找", state_key="findStatus",
            on_change={"findStatus": 1}, off_change={"findStatus": 0}),
    ),
)
