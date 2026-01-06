# Panasonic Smart China for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![Co-created with](https://img.shields.io/badge/Co--created%20with-Gemini%203%20Pro-8E75B2)]()

这是一个用于 Home Assistant 的自定义集成插件，专为**中国大陆地区**使用 **“松下智能家电” (Panasonic Smart China)** 进行控制的空调设备开发。

> 💡 **特别致谢**：本项目由开发者与 Google **Gemini 3 Pro** 深度协作完成。从工程搭建、设备 Token 算法破解、到复杂的 Read-Modify-Write 原子控制逻辑，均由 AI 辅助实现。
> 💡 **特别致谢**：登陆算法由arthurfsy和不知名的逆向大佬提供。

## ✨ 核心特性

本插件解决了官方 App 功能简陋及接入 HA 困难的诸多痛点：

* **无需抓包，自动获取 Token**：
    * 内置双重 SHA-512 签名算法，只需输入账号密码，插件自动计算设备控制 Token。
* **会话自动保持 (Anti-Kickout)**：
    * 实现了智能的 Session 缓存机制。在添加多台设备时，自动复用登录凭证，彻底解决因重复登录导致“账号互踢/掉线”的问题。
* **原子化控制逻辑 (Read-Modify-Write)**：
    * 在发送指令前毫秒级读取设备最新状态，防止因 HA 状态延迟导致覆盖了物理遥控器的操作（如：不会意外关闭刚打开的静音模式）。
* **完美的静音与风速映射**：
    * **静音模式**：独立映射为 `Quiet` 风速。选中时自动发送 `{windSet: 10, muteMode: 1}` 组合指令；切换其他风速时自动关闭静音。
    * **常规风速**：完美支持 自动/低/中/高/超强 等档位。
* **高频状态同步**：
    * 内置 30秒/次 的主动轮询机制，实现秒级状态反馈（UI 跟手感极佳）。
* **外部传感器绑定**：
    * 支持将空调关联到 HA 中的任意温度传感器（如米家、SHT30），解决空调自带回风温度不准的问题。

## 📋 适用设备

* **App**：仅支持中国区“松下智能家电” App（蓝色图标）。不支持国际版 Comfort Cloud。
* **控制器**：默认适配 `CZ-RD501DW2` 线控器（常见于松下家用中央空调/风管机）。
    * *支持通过配置文件扩展其他型号。*

## 🚀 安装方法

### 方法一：HACS 安装 (推荐)

1.  打开 HACS -> **Integrations (集成)**。
2.  点击右上角菜单 -> **Custom repositories (自定义存储库)**。
3.  填入本项目 GitHub 地址，类别选择 **Integration**。
4.  搜索 `Panasonic Smart China` 点击下载。
5.  重启 Home Assistant。

### 方法二：手动安装

1.  下载本项目源码。
2.  将 `panasonic_smart_china` 文件夹完整复制到您的 HA 配置目录 `/config/custom_components/` 下。
3.  确保路径为：`/config/custom_components/panasonic_smart_china/__init__.py` (注意文件夹名称必须完全一致)。
4.  重启 Home Assistant。

## ⚙️ 配置指南

1.  进入 **配置** -> **设备与服务** -> **添加集成**。
2.  搜索 **Panasonic Smart China**。

### 步骤 1：登录
输入您在松下 App 的**手机号**和**密码**。
> *注：首次登录会自动缓存会话，添加第二台设备时将跳过登录直接选择设备。*
> *注：Panasonic Smart China只允许单点登录，配置到HA后，如手机再次登陆则HA会失效。*

### 步骤 2：设备配置
* **选择设备**：下拉选择要添加的空调。
* **控制器型号**：保持默认 `CZ-RD501DW2`（除非您确信是其他型号）。
* **温度传感器**：(可选) 选择一个房间内的温度实体，用于在空调卡片上显示真实室温。

## 🎮 使用技巧

### 关于静音模式
由于松下协议中“静音”是一个独立开关而非风速档位，本插件将其逻辑化处理：
* **开启静音**：在风速列表中选择 **Quiet (静音)**。
* **关闭静音**：选择任意其他风速（如 Auto, Low），插件会自动关闭静音开关。

### 关于温度步长
插件已强制将温度调节步长设为 **1.0°C**，以符合大多数松下线控器的实际操作逻辑。

## 🔧 高级：扩展控制器支持

如果您使用的是非 `CZ-RD501DW2` 型号的控制器，且发现风速或模式不对应，可以在 `const.py` 文件中扩展配置：

```python
SUPPORTED_CONTROLLERS = {
    "YOUR_NEW_MODEL": {
        "name": "您的新型号名称",
        "temp_scale": 2, # 温度倍率 (松下通常是2)
        "hvac_mapping": { ... }, # 模式映射表
        "fan_mapping": { ... },  # 风速映射表
        "fan_payload_overrides": { ... } # 特殊指令覆盖
    },
    ...
}
```

## ⚠️ 免责声明
* 本项目为开源社区作品，非松下官方开发。
* 插件通过模拟 App API 请求实现功能，虽然内置了防封禁优化（轮询间隔限制），但仍请合理使用。
* 因使用本项目导致的设备异常或账号问题，开发者不承担责任。

**Created with ❤️ by Developer & Gemini 3 Pro**