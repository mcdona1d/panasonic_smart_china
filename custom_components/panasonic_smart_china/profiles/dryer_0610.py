"""烘干机 profile（已按你的抓包数据填好）。

品类代号 0610   子类 43   (deviceId 形如 <MAC>_0610_03-03)
状态接口: WDevGetStatusInfoBD158（与洗衣机同接口，字段侧重不同）
枚举取自设备自带 JS: ca/cn/0610/43/js/common/constants.js
只读传感器。
"""
from __future__ import annotations

from ..models import (
    ENTITY_KIND_DRYER,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PROTOCOL_GENERIC_STATUS,
    PanasonicEndpoint,
    PanasonicNumberDescription,
    PanasonicProfile,
    PanasonicSelectDescription,
    PanasonicSensorDescription,
    PanasonicSwitchDescription,
)

DRY_PROGRAM = {
    1: "棉织物", 2: "化纤", 3: "羊毛", 4: "丝绸内衣", 5: "运动服", 6: "衬衫",
    7: "混合", 8: "羽绒服", 9: "筒洗净", 11: "大物", 13: "超快速", 15: "除菌烘",
    23: "nanoeX除菌", 24: "户外服", 25: "牛仔", 27: "nanoeX除味", 36: "定时烘",
    44: "自投入保养", 50: "nanoeX防过敏", 51: "nanoeX除皱", 52: "nanoeX蓬松",
    53: "nanoeX皮毛", 57: "暖衣", 61: "nanoeX棉织物", 63: "一键智烘", 71: "浴巾/毛巾",
    72: "婴童装", 73: "随心烘", 74: "nanoeX一键智护", 75: "定时暖风", 77: "定时冷风",
    79: "焕新空气洗", 80: "工装校服", 81: "夜间烘", 82: "暖被", 83: "热风暖衣",
    86: "nanoeX西装/风衣", 87: "nanoeX丝绒", 88: "nanoeX丝绸", 89: "nanoeX蚕丝被",
    90: "nanoeX夏凉被", 91: "nanoeX羊绒", 92: "nanoeX雪纺纱", 93: "nanoeX摇粒绒",
    94: "nanoeX冲锋衣", 95: "nanoeX毛绒玩具", 96: "nanoeX皮包", 97: "10分钟除皱",
    98: "浴巾",
}

RUN_STAGE = {
    0: "电源待机", 1: "初期设定", 2: "运转中",
    3: "预约中", 4: "预约中", 5: "运转终了",
    6: "异常中", 7: "中途关机",
}
DRY_MODE = {0: "无", 1: "熨衣", 2: "即穿", 3: "入柜", 4: "暖衣"}
DRY_TEMP = {1: "40℃", 2: "45℃", 3: "50℃", 4: "55℃", 5: "60℃", 6: "65℃"}
DRY_TYPE = {1: "低温", 2: "节能", 3: "快速"}

DRYER_0610_PROFILE = PanasonicProfile(
    profile_id="dryer_0610",
    controller_model="松下烘干机-0610",
    name="松下烘干机 (0610)",
    category_ids=frozenset({"0610"}),
    ha_platforms=(PLATFORM_SENSOR, PLATFORM_SWITCH, PLATFORM_SELECT, PLATFORM_NUMBER),
    entity_kind=ENTITY_KIND_DRYER,
    protocol=PROTOCOL_GENERIC_STATUS,
    status_endpoint=PanasonicEndpoint(
        path="WDevGetStatusInfoBD158",
        request_id=100,
        require_results=True,
        required_result_keys=frozenset({"runingStatus"}),
    ),
    set_endpoint=PanasonicEndpoint(
        path="WDevSetStatusInfoCommon",
        request_id=200,
        require_results=False,
        allow_non_json_response=True,
    ),
    sensor_descriptions=(
        PanasonicSensorDescription(
            key="run_stage", source_key="runingStage",
            name="运转阶段", value_map=RUN_STAGE),
        PanasonicSensorDescription(
            key="remaining_time", source_key="runingTimeResidual",
            name="剩余时间", unit="min", device_class="duration"),
        PanasonicSensorDescription(
            key="dry_mode", source_key="dryMode",
            name="干衣模式", value_map=DRY_MODE),
        PanasonicSensorDescription(
            key="dry_temp", source_key="dryTemp",
            name="干衣温度", value_map=DRY_TEMP),
        PanasonicSensorDescription(
            key="dry_type", source_key="dryType",
            name="运转模式", value_map=DRY_TYPE),
        PanasonicSensorDescription(
            key="child_lock", source_key="childLock",
            name="童锁", value_map={0: "关", 1: "开"}),
        PanasonicSensorDescription(
            key="care_agent_lack", source_key="careAgentLack",
            name="护理剂不足", value_map={0: "充足", 1: "不足"}),
        PanasonicSensorDescription(
            key="remote_enable", source_key="remoteEnable",
            name="远程可控", value_map={0: "否", 1: "是"}),
        PanasonicSensorDescription(
            key="gate_status", source_key="gateStatus",
            name="舱门状态", value_map={0: "打开", 1: "关闭"}),
        PanasonicSensorDescription(
            key="remote_status", source_key="remoteStatus",
            name="远程控制已开启", value_map={0: "否", 1: "是"}),
    ),
    control_switches=(
        PanasonicSwitchDescription(
            key="power", name="电源",
            state_key="runingStage",
            state_on=frozenset({1, 2, 3, 4, 5}),
            on_change={"powerStatus": 1, "runingStatus": 0},
            off_change={"powerStatus": 0},
        ),
        PanasonicSwitchDescription(
            key="run", name="开始/暂停",
            state_key="runingStatus",
            state_on=frozenset({1}),
            on_change={"powerStatus": 1, "runingStatus": 1},
            off_change={"runingStatus": 0},
            require_door_closed=True,
        ),
        PanasonicSwitchDescription(
            key="child_lock", name="童锁", state_key="childLock",
            on_change={"childLock": 1}, off_change={"childLock": 0}),
        PanasonicSwitchDescription(
            key="nanoe", name="nanoeX", state_key="nanoe",
            on_change={"nanoe": 1}, off_change={"nanoe": 0}),
        PanasonicSwitchDescription(
            key="mute", name="静音", state_key="mute",
            on_change={"mute": 1}, off_change={"mute": 0}),
    ),
    control_selects=(
        PanasonicSelectDescription(
            key="program", source_key="program",
            name="烘干程序", options=DRY_PROGRAM),
        PanasonicSelectDescription(
            key="dry_mode", source_key="dryMode",
            name="干衣模式", options=DRY_MODE),
        PanasonicSelectDescription(
            key="dry_temp", source_key="dryTemp",
            name="干衣温度", options=DRY_TEMP),
        PanasonicSelectDescription(
            key="dry_type", source_key="dryType",
            name="运转模式", options=DRY_TYPE),
    ),
    control_numbers=(
        PanasonicNumberDescription(
            key="dry_time", source_key="dryTime", name="定时烘干时长",
            min_value=0, max_value=240, step=10, unit="min", device_class="duration"),
    ),
)
