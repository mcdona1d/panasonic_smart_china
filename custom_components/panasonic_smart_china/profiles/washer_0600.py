"""洗衣机 profile（已按你的抓包数据填好）。

品类代号 0600   子类 42   (deviceId 形如 <MAC>_0600_03-03)
状态接口: WDevGetStatusInfoBD158  (返回 135 个字段)
枚举含义取自设备自带 JS: ca/cn/0600/42/js/common/constants.js
只读，不做控制（洗衣机远程启停云端一般不放开）。
"""
from __future__ import annotations

from ..models import (
    ENTITY_KIND_WASHER,
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

WASH_PROGRAM = {
    0: "一键智洗", 1: "棉织物", 2: "化纤", 3: "羊毛", 4: "丝绸内衣", 5: "运动服",
    6: "衬衫", 7: "混合", 8: "羽绒服", 9: "筒洗净", 11: "大物", 12: "顽渍洗",
    13: "超快速", 15: "95℃除菌", 16: "节能洗", 21: "随心洗", 22: "超柔",
    23: "nanoeX除菌", 24: "户外服", 25: "牛仔", 26: "除螨", 27: "nanoeX除味",
    28: "nanoeX防霉", 29: "净漂", 30: "亮彩", 32: "单漂洗", 33: "单脱水",
    34: "自动干衣", 35: "低温干衣", 36: "定时烘", 37: "单干衣", 44: "智能投放保养",
    45: "清屑洁筒", 50: "nanoeX防过敏", 51: "nanoeX除皱", 52: "nanoeX蓬松",
    53: "nanoeX皮毛", 57: "暖衣", 58: "空气洗", 59: "漂+脱", 60: "除菌空气洗",
    61: "nanoeX棉麻", 71: "浴巾/毛巾", 72: "婴童装", 78: "除螨洗", 80: "工装校服",
    82: "晒被", 86: "nanoeX西装/风衣", 87: "nanoeX丝绒", 88: "nanoeX丝绸",
    89: "nanoeX蚕丝被", 90: "nanoeX夏凉被", 91: "nanoeX羊绒", 92: "nanoeX雪纺纱",
    93: "nanoeX摇粒绒", 94: "nanoeX冲锋衣", 95: "nanoeX毛绒玩具", 96: "nanoeX皮包",
}

RUN_STAGE = {
    0: "电源待机", 1: "初期设定", 2: "运转中",
    3: "预约中", 4: "预约中", 5: "运转终了",
    6: "异常中", 7: "中途关机",
}
WASH_MODE = {0: "洗涤", 1: "洗干", 2: "烘干", 3: "护理", 4: "健康", 5: "塑形", 6: "顽渍"}
WASH_TEMP = {0: "冷水", 1: "30℃", 2: "40℃", 3: "50℃", 4: "60℃", 6: "70℃", 7: "80℃", 8: "90℃", 9: "95℃"}
SPIN_SPEED = {0: "500r/min", 2: "700r/min", 4: "900r/min", 5: "1000r/min",
              7: "1200r/min", 9: "1400r/min", 10: "1500r/min", 11: "1600r/min", 15: "关"}
WATER_LEVEL = {0: "少量", 1: "低", 2: "中", 4: "高"}
DOSE_LEVEL = {0: "关", 1: "低", 2: "中", 3: "高"}
ONOFF = {0: "否", 1: "是"}

WASHER_0600_PROFILE = PanasonicProfile(
    profile_id="washer_0600",
    controller_model="松下滚筒洗衣机-0600",
    name="松下洗衣机 (0600)",
    category_ids=frozenset({"0600"}),
    ha_platforms=(PLATFORM_SENSOR, PLATFORM_SWITCH, PLATFORM_SELECT, PLATFORM_NUMBER),
    entity_kind=ENTITY_KIND_WASHER,
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
            key="total_time", source_key="runingTimeTotal",
            name="总时间", unit="min", device_class="duration"),
        PanasonicSensorDescription(
            key="wash_mode", source_key="washMode",
            name="洗涤模式", value_map=WASH_MODE),
        PanasonicSensorDescription(
            key="temperature", source_key="temperature",
            name="洗涤温度", value_map=WASH_TEMP),
        PanasonicSensorDescription(
            key="spin_speed", source_key="spinSpeed",
            name="脱水转速", value_map=SPIN_SPEED),
        PanasonicSensorDescription(
            key="water_level", source_key="waterLevel",
            name="水位", value_map=WATER_LEVEL),
        PanasonicSensorDescription(
            key="detergent_level", source_key="detergentLevel",
            name="洗涤剂投放量", value_map=DOSE_LEVEL),
        PanasonicSensorDescription(
            key="softener_level", source_key="softenerLevel",
            name="柔顺剂投放量", value_map=DOSE_LEVEL),
        PanasonicSensorDescription(
            key="detergent_lack", source_key="detergentLack",
            name="洗涤剂不足", value_map={0: "充足", 1: "不足"}),
        PanasonicSensorDescription(
            key="softener_lack", source_key="softenerLack",
            name="柔顺剂不足", value_map={0: "充足", 1: "不足"}),
        PanasonicSensorDescription(
            key="child_lock", source_key="childLock",
            name="童锁", value_map={0: "关", 1: "开"}),
        PanasonicSensorDescription(
            key="remote_enable", source_key="remoteEnable",
            name="远程可控", value_map=ONOFF),
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
            key="pre_wash", name="预洗", state_key="preWash",
            on_change={"preWash": 1}, off_change={"preWash": 0}),
        PanasonicSwitchDescription(
            key="extra_rinse", name="加漂洗", state_key="extraRinse",
            on_change={"extraRinse": 1}, off_change={"extraRinse": 0}),
        PanasonicSwitchDescription(
            key="nanoe", name="nanoeX", state_key="nanoe",
            on_change={"nanoe": 1}, off_change={"nanoe": 0}),
        PanasonicSwitchDescription(
            key="easy_ironing", name="轻柔免熨", state_key="easyIroning",
            on_change={"easyIroning": 1}, off_change={"easyIroning": 0}),
        PanasonicSwitchDescription(
            key="mute", name="静音", state_key="mute",
            on_change={"mute": 1}, off_change={"mute": 0}),
        PanasonicSwitchDescription(
            key="ag_plus", name="Ag+除菌", state_key="agPlus",
            on_change={"agPlus": 1}, off_change={"agPlus": 0}),
        PanasonicSwitchDescription(
            key="active_foam", name="智能泡沫", state_key="activeFoam",
            on_change={"activeFoam": 1}, off_change={"activeFoam": 0}),
    ),
    control_selects=(
        PanasonicSelectDescription(
            key="program", source_key="program",
            name="洗涤程序", options=WASH_PROGRAM),
        PanasonicSelectDescription(
            key="temperature", source_key="temperature",
            name="洗涤温度", options=WASH_TEMP),
        PanasonicSelectDescription(
            key="spin_speed", source_key="spinSpeed",
            name="脱水转速", options=SPIN_SPEED),
        PanasonicSelectDescription(
            key="water_level", source_key="waterLevel",
            name="水位", options=WATER_LEVEL),
    ),
    control_numbers=(
        PanasonicNumberDescription(
            key="rinse_times", source_key="rinseTime", name="漂洗次数",
            min_value=0, max_value=5, step=1, unit="次"),
    ),
)
