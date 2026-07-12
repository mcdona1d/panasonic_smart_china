"""models.py 的改动说明。

★ 推荐做法：直接用 skeleton/models.py 整文件覆盖 custom_components/panasonic_smart_china/models.py，
   不用手动合并（改动较多，手动容易漏，之前"Invalid handler specified"多半就是这个原因）。★

本文件仅作为"改了哪些"的清单参考。相比原版 models.py，新增了：

1) 平台常量：
   PLATFORM_SENSOR = "sensor"
   PLATFORM_SWITCH = "switch"
   PLATFORM_NUMBER = "number"
   PLATFORM_SELECT = "select"

2) 设备类型 / 协议常量：
   ENTITY_KIND_WASHER / ENTITY_KIND_DRYER / ENTITY_KIND_FRIDGE / ENTITY_KIND_KNOB
   PROTOCOL_GENERIC_STATUS

3) 四个描述 dataclass：
   PanasonicSensorDescription   —— 传感器字段
   PanasonicSwitchDescription   —— 开关（洗衣机电源/开始暂停、冰箱布尔开关、旋钮找一找）
   PanasonicNumberDescription   —— 数值（冰箱温度）
   PanasonicSelectDescription   —— 下拉（洗衣机/烘干机程序）

4) 给 PanasonicProfile 追加四个字段（都有默认值 ()，向后兼容）：
   sensor_descriptions / control_switches / control_numbers / control_selects

完整定义见 skeleton/models.py。
"""
