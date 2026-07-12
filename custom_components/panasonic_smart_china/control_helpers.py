"""Shared control payload builders for Panasonic Smart China.

build_control_payload() constructs the write-request body per device family using
Read-Modify-Write. Payload shapes differ by category:
  - washer/dryer: WDevSetStatusInfoCommon, a full settings object (fields from device JS)
  - fridge:       FDevSetStatusInfoMqtt, a full status subset (fields from capture)
  - knob:         WDevSetKnobStatus, only the changed fields
"""

from __future__ import annotations

_WASHER_CYCLE_SOURCE = {
    "washCycle": "washCycleCur",
    "rinseCycle": "rinseCycleCur",
    "spinCycle": "spinCycleCur",
    "dryCycle": "dryCur",
    "preWashCycle": "preWashCur",
    "easyIroningCycle": "easyIroningCur",
    "nanoeCycle": "nanoe",
    "supplyAirCycle": "supplyAirCur",
    "coolCycle": "coolCur",
    "selfPutCycle": None,
    "bitsCleanCycle": "bitsClog",
    "preHandleCycle": "preHandleCur",
}
_WASHER_SET_KEYS = (
    "washTime", "rinseTime", "spinTime", "dryTime", "preWash", "easyIroning",
    "nanoe", "spinSpeed", "waterLevel", "temperature", "mute", "activeFoam",
    "cycpump", "agPlus", "childLock", "timeDelayTotal", "extraRinse", "dryType",
    "washMode", "dryMode", "dryTemp", "waterLevelSwitch", "runTimeSwitch",
    "stainsType", "washDryLinkage", "voiceSwitch",
)

_FRIDGE_SET_KEYS = (
    "PCTempSet", "PCTempCur", "PCTempCurAlarm",
    "SCS1TempSet", "SCS1TempCur", "SCS1TempCurAlarm",
    "SCS2TempSet", "SCS2TempCur", "SCS2TempCurAlarm",
    "SCB1TempSet", "SCB1TempCur", "SCB1TempCurAlarm",
    "SCB2TempSet", "SCB2TempCur", "SCB2TempCurAlarm",
    "FCTempSet", "FCTempCur", "FCTempCurAlarm",
    "quickFreeze", "vacation", "quickicing", "icingStop", "icingDeice",
    "eraseOdor", "ecoNaviSet", "speed", "RAModeCur", "SAModeCur",
    "bodyOperating", "iceDetection", "waterLack", "silver", "preservation",
    "nanoe", "freshFrozen", "smartHumi", "autoIcing", "WCModeCur",
    "SCB1ModeCur", "SCB2ModeCur", "PCGate1", "PCGate2", "SCGate",
    "SCB1Gate", "SCB2Gate", "FCGate1", "FCGate2", "ICGate", "gateAlarm",
    "ecoMode", "bodyOffline", "waterFresh", "PCMicroFreeze", "SCS1DryStore",
    "perfection", "smartsHumSense", "moodLighting", "waterGiveLack",
)


def _build_washer_settings(status: dict) -> dict:
    s = {"program": status.get("program", 0)}
    for setk, src in _WASHER_CYCLE_SOURCE.items():
        s[setk] = status.get(src, 0) if src else 0
    for k in _WASHER_SET_KEYS:
        if k in status:
            s[k] = status[k]
    s["powerStatus"] = 1
    s["runingStatus"] = status.get("runingStatus", 0)
    return s


def _build_fridge_settings(status: dict) -> dict:
    return {k: status.get(k, 0) for k in _FRIDGE_SET_KEYS}


def build_control_payload(entity_kind: str, status: dict, change: dict) -> dict:
    """按品类构建写请求 params，并叠加要改动的字段 change。"""
    status = status or {}
    if entity_kind in ("washer", "dryer"):
        params = _build_washer_settings(status)
    elif entity_kind == "fridge":
        params = _build_fridge_settings(status)
    else:
        params = {}
    params.update(change)
    return params
