# VRun

Windows 桌面虚拟跑步与定位模拟工具，支持路线选择、速度与配速设置、记圈、距离提醒及运动轨迹可视化。

## 系统支持

| 手机系统 | 连接方式 | 要求 |
| --- | --- | --- |
| iOS 15–16 | USB | 对应开发者镜像；iOS 16 开启开发者模式 |
| iOS 17.0–17.3 | RemoteXPC / QUIC 隧道 | 管理员权限、Apple 网络设备驱动及 IPv6 |
| iOS 17.4 及以上 | USB 用户态隧道 | 开启开发者模式，通常无需管理员权限 |

iOS 17+ 处于实验支持阶段，尚未完成真机验证。首次准备开发者镜像可能需要联网；早期 iOS 17 所需的额外网络驱动需自行配置。

## 安装与使用

运行 Windows x64 安装包。安装包内置运行环境，无需另行安装 Python 或运行 pip。安装器会复用已有 Apple 通信组件，缺少时从官方地址下载、验证签名并安装；此过程需要网络和管理员权限。

1. 通过 USB 连接并解锁 iPhone，确认“信任此电脑”。iOS 16 及以上需在“设置 → 隐私与安全性”中开启开发者模式。
2. 选择路线并输入速度，单位为 m/s，旁边显示每公里配速。
3. 按需启用距离提醒，选择 2 km、3 km 或输入自定义公里数。
4. 点击“开始”；结束时点击“停止并恢复定位”。

速度按实际经过时间推进，并计入设备通信耗时；手机应用测得的速度仍受坐标采样和应用算法影响。通信长时间无响应时会停止模拟并尝试恢复定位。

达到目标距离后提醒一次并继续运行。Windows 通知可能受系统设置或请勿打扰模式影响。界面支持跟随系统、浅色和深色主题。

升级前先停止运动并关闭软件，再运行新安装包。覆盖安装会沿用安装目录并保留路线及设置；如先卸载旧版，请备份 routes。卸载 VRun 不会卸载 Apple 驱动。

## 路线与统计

routes 预置 HNroute.txt、ZJG-west.txt、ZJG-east.txt，默认选择东区路线。将兼容的 UTF-8 .txt 文件放入该目录后重启即可选择。

路线使用上游的 BD-09 坐标格式，由 lat、lng 字典组成；软件会转换为 WGS-84 并闭合路线。不要直接导入 WGS-84 坐标。

每完成一次完整路线循环记一圈。“模拟估算距离”按完成圈数乘以路线长度计算，每圈更新一次，因此距离提醒可能延迟不到一圈。图中显示本次模拟位置和本圈进度，不是手机实时 GPS 数据，也不代表其他应用统计的运动量。

## 故障排查

- 无法连接：检查 USB、手机解锁与信任状态、开发者模式及 Apple 驱动。
- 恢复定位失败：连接同一台手机，再次点击“停止并恢复定位”。正常关闭窗口也会尝试恢复；断电、拔线或强制结束程序时无法保证恢复。
- 日志：应用日志位于 %LocalAppData%\VRun；驱动安装日志位于 %ProgramData%\VRun\driver-install.log。
- 设置保存在当前用户的 Software\VRun\VRun 注册表项；iOS 17+ 镜像和配对缓存由 pymobiledevice3 管理。

## 开发与构建

需要 Windows x64、Python 3.14 和 Inno Setup 6/7：

    python -m pip install -r requirements-dev.txt
    python main.py
    python -m pytest -q
    python scripts/build.py --installer

应用输出到 dist/VRun，安装包输出到 release。可通过 INNO_ISCC 指定 Inno Setup 编译器。requirements-ios17.txt 固定独立定位组件的依赖版本。

## 来源与许可

基于 [iOSRealRun-cli](https://github.com/iOSRealRun/iOSRealRun-cli)，参考 [iOSRealRun-cli-17](https://github.com/iOSRealRun/iOSRealRun-cli-17) 接入 iOS 17+。

桌面应用采用 MPL-2.0，独立 ios17_helper 组件采用 GPL-3.0-or-later。第三方组件保留各自许可，详见 [UPSTREAM.md](UPSTREAM.md)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 LICENSES。安装包 SOURCE 目录提供对应源码。
