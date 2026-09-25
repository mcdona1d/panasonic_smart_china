# Panasonic Smart China for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-2.1.0-blue.svg)]()
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

这是一个用于 Home Assistant 的松下中国区智能家电自定义集成，目标是逐步维护成面向“松下智能家电”中国区设备的核心 HA 集成仓库。

项目当前基于对“松下智能家电”App 通信逻辑的分析实现，非松下官方项目。目前已支持品类代号 `0900` 的松下风管机/中央空调线控设备，以及品类代号 `0820` 的 `FV-RB20VL1` 风暖浴霸。代码内部采用 profile 驱动模型，后续会通过独立 profile、协议端点和 HA entity adapter 扩展更多品类和设备型号。

> 💡 特别致谢：登陆算法由arthurfsy和不知名的逆向大佬提供。

> 💡 风暖浴霸 `FV-RB20VL1` 的核心控制逻辑提取自 [YUAN121300/panasonic_smart_china_Aircle](https://github.com/YUAN121300/panasonic_smart_china_Aircle)。感谢该项目作者对浴霸协议、模式映射、控制参数以及必要请求头的分析与验证。

## 当前状态

2.1 版本在账号级配置模型基础上新增了多品类 profile/adapter 扩展层，并加入风暖浴霸支持：

- 在 HA 中以松下账号为配置入口。
- 登录后自动扫描账号下可识别的设备。
- 每个设备会在同一账号配置项下创建对应实体。
- 当前已注册 `0900` 风管机和 `0820` `FV-RB20VL1` 风暖浴霸 profile。
- profile 可以声明品类代号、型号匹配、HA 平台、实体 adapter、状态读取接口、控制接口和安全写入字段。
- 初始化流程只允许选择已支持设备，并会列出因 category 或具体型号不受支持而被过滤的设备。
- 设备信息会透出设备名称、厂商和型号，便于在 HA 设备页识别。

## 重要升级说明

2.0 是一次不兼容升级，不会迁移 1.x 中按单设备创建的旧配置。

从 1.x 升级时建议按以下流程处理：

1. 在 HA 中删除旧的实体、设备和集成配置。
2. 上传或通过 HACS 更新到 2.0 代码。
3. 重启 Home Assistant。
4. 使用松下账号重新添加集成。
5. 检查自动化、仪表盘、HomeKit、场景中对旧 entity id 的引用。

这样做会牺牲旧实体的连续性，但可以避免复杂迁移逻辑引入不可控问题，也更适合后续多品类扩展。

## 功能特性

- 账号级配置：一次登录账号，扫描并挂载账号下的可支持设备。
- 自动获取控制 token：内置松下设备控制所需的签名和 token 计算逻辑。
- 单点登录提醒：松下账号存在单点登录限制，如果手机 App 重新登录导致 HA 会话失效，集成会触发重新认证提醒。
- Read-Modify-Write 控制：发送控制指令前先读取设备当前状态，再只修改必要字段，降低覆盖设备真实状态的风险。
- 0900 风管机控制：支持开关机、制冷、制热、除湿、自动模式、目标温度和风速控制。
- FV-RB20VL1 风暖浴霸控制：支持待机、取暖、换气、凉干燥和热干燥模式。
- 静音风速映射：将松下协议中的静音开关映射为 HA 中的 `Quiet` 风速。
- 外部温度传感器：可为 climate 实体绑定 HA 中的温度传感器，用于显示更准确的室内温度。
- 本地品牌图：包含 HA 自定义集成可加载的本地 `brand/icon.png` 和 `brand/logo.png`。

## 已验证设备

| 品类代号 | 设备类型 | 当前 profile | 说明 |
| --- | --- | --- | --- |
| `0900` | 风管机/中央空调 | `ducted_ac_0900` | 以 `CZ-RD501DW2` 线控器逻辑验证 |
| `0820` | 风暖浴霸 | `bathroom_heater_0820_fv_rb20vl1` | 支持型号 `FV-RB20VL1`，设备 ID 后缀可能显示为 `Aircle-05-02` |

其他品类和型号暂未声明支持。即使能在扫描中识别出来，也需要补充 profile/adapter 并完成真实设备验证后再开放。

## 安装方式

### 兼容性

* Home Assistant Core 2026.8.0 或更高版本。
* 2.1.1 起使用 2026.8 引入的 `DeviceInfo.via_device_id`，不再兼容 2026.7 及更早版本。

### HACS 自定义仓库

1. 打开 HACS。
2. 进入 Integrations。
3. 右上角菜单选择 Custom repositories。
4. 添加本仓库地址，类别选择 Integration。
5. 搜索并安装 Panasonic Smart China。
6. 重启 Home Assistant。

### 手动安装

1. 下载本仓库代码。
2. 将 `custom_components/panasonic_smart_china` 复制到 HA 配置目录的 `/config/custom_components/` 下。
3. 确认路径为 `/config/custom_components/panasonic_smart_china/manifest.json`。
4. 重启 Home Assistant。

## 配置方式

1. 打开 Home Assistant。
2. 进入 设置 -> 设备与服务 -> 添加集成。
3. 搜索 Panasonic Smart China。
4. 输入“松下智能家电”中国区账号和密码。
5. 选择需要启用的设备。
6. 如有需要，为 climate 设备绑定一个 HA 温度传感器。

注意：松下账号是单点登录模式。HA 登录后，手机 App 可能会被踢下线；手机 App 重新登录后，HA 也可能失效。出现重新认证提醒时，需要在 HA 中重新登录账号。

## 使用说明

### 温度控制

当前 0900 风管机 profile 使用 1°C 温度步长，支持 16°C 到 30°C 的目标温度范围。

设备关机时，集成会忽略来自 HA 的目标温度写入，避免某些场景在发送 `off` 的同时携带温度并污染下次开机温度。

### 风速与静音

常规风速映射为：

- `Auto`
- `Min`
- `Low`
- `Medium`
- `High`
- `Max`

静音模式在 HA 中显示为 `Quiet`。选择 `Quiet` 时会发送松下协议需要的组合参数；切换到任意常规风速时会关闭静音。

### 外部温度传感器

选项页中可以为 climate 实体绑定一个 HA 温度传感器。选择器只会展示 device class 为 `temperature` 的 sensor，避免误选非温度实体。

当前暂不支持外部湿度传感器。

### 风暖浴霸

`FV-RB20VL1` 在 HA 中映射为 climate 实体，支持取暖、换气、凉干燥、热干燥和待机模式。

仪表盘配置示例见 [风暖浴霸仪表盘卡片](guides/风暖浴霸仪表盘卡片.md)。

## 开发方向

后续计划围绕三个方向推进：

1. 稳定 0900 风管机控制链路，持续收敛 read/write、会话失效、异常状态处理。
2. 基于当前 profile 模型继续补齐不同 HA 平台的 adapter，例如 climate、sensor、switch、select、number 等。
3. 吸收社区贡献的设备适配逻辑，逐步扩展为松下中国区 HA 集成的核心仓库。

当前新增设备适配的推荐路径：

1. 新建设备 profile，声明 `profile_id`、`category_ids`、可选 `model_ids`、HA 平台、实体类型、状态读取接口、控制接口和响应校验字段。
2. 如果已有 HA 平台和实体类型可以复用，只补 profile；如果能力模型不同，再新增对应的 entity adapter。
3. API 层只增加协议端点和 header 差异，不直接写 HA 状态映射。
4. 配置流通过 profile 注册表自动发现可支持设备，不为单个型号写特殊分支。

适配新设备时，请尽量提供：

- 设备品类代号和型号信息。
- App 中展示的设备名称和控制能力。
- 状态读取返回字段。
- 控制指令前后的 payload 差异。
- 已验证的真实设备行为。

## 许可与适配代码回流

本项目采用 [Apache License 2.0](LICENSE)。

选择 Apache-2.0 的主要原因：

- 它是宽松开源许可证，允许使用、复制、修改、合并和再分发代码。
- 它包含明确的贡献定义和贡献授权条款，适合社区通过 PR、issue 或代码片段提交适配逻辑。
- 它包含明确的专利授权条款，比 MIT 在长期维护和多贡献者场景下更稳妥。
- Home Assistant Core 本身也采用 Apache-2.0，未来如果需要向 HA 生态更深整合，许可摩擦更少。

除非提交者明确标注 `Not a Contribution`，否则提交到本仓库的 Pull Request、issue、讨论、代码片段、设备 profile、adapter 和协议字段说明，均视为愿意按 Apache-2.0 授权给本项目使用。维护者可以基于这些内容提取、改写、合并设备适配逻辑，并发布到本仓库的后续版本中。

如果你从本仓库 fork 或 clone 后公开发布了新的适配代码，只要这些代码仍按 Apache-2.0 或兼容许可发布，本项目也可以在保留必要版权和许可声明的前提下吸收相关适配逻辑。该许可不会强制 fork 主动回流代码；如果你希望设备适配进入主仓，请优先提交 Pull Request。

## 免责声明

- 本项目不是松下官方项目，也未获得松下官方背书。
- Panasonic、松下及相关产品名称归其权利人所有，本项目仅为说明兼容对象而使用这些名称。
- 本项目通过模拟 App API 请求实现设备控制，相关接口可能被官方随时调整。
- 使用本项目导致的账号异常、设备异常、自动化误动作或其他损失，项目维护者不承担责任。
- 请合理控制轮询频率和自动化触发频率，避免对服务端造成不必要压力。
