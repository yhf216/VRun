# VRun

Windows 桌面虚拟跑步与定位模拟工具。基于 iOSRealRun/iOSRealRun-cli，并参考 iOSRealRun-cli-17 接入 iOS 17+ 开发者隧道。iOS 15–16 保留原有实现；iOS 17+ 为待真机验收的实验适配。

## 0.3.0：iOS 17+ 实验适配

- 自动根据设备版本选择后端。iOS 17 以下仍使用原来的 libimobiledevice、镜像目录和定位命令；不会加载新增的 Python 通信库。
- iOS 17+ 通过独立的 VRun-iOS17 组件维持一条开发者隧道与定位会话，复用现有路线、速度、计圈、提醒及动画。停止时先恢复定位，再释放连接。
- 固定 pymobiledevice3 11.44.0 及依赖快照，安装包内置运行环境，不需要用户额外运行 pip。已有个性化镜像可复用；缺少时由依赖准备，首次可能需要联网下载并请求 Apple 个性化服务。
- 增加版本分流、隧道协议选择、镜像复用、设备标识、取消清理及异常恢复测试。此处的自动化验证不等于 iOS 17+ 真机验证。

| 手机系统 | 连接方式 | 额外条件 |
| --- | --- | --- |
| iOS 15–16 | 原有 USB 定位流程 | 对应 DeveloperDiskImage；iOS 16 开启开发者模式 |
| iOS 17.0–17.3 | RemoteXPC / QUIC 内核隧道 | 以管理员身份运行；Apple 网络设备驱动及 IPv6 可用 |
| iOS 17.4 及以上 | USB CoreDeviceProxy / 用户态隧道 | 通常不需要管理员权限；开启开发者模式 |

早期 iOS 17 的额外网络驱动不由本版自动替换或强制重装。若 USB 信息可读但找不到 RemoteXPC，请检查设备管理器、Apple 网络设备、IPv6 以及 iTunes/Apple Devices 安装。本版不承诺所有后续 iOS 小版本、硬件或预览版均可用。

## 保留的界面功能

- 新增“跟随系统／浅色／深色”外观选择，默认跟随 Windows 应用主题。主按钮和运动轨迹适配 Windows 强调色，深色模式会提高文字和路径对比度；标题栏同步明暗。手动选择会保存，不会修改 Windows 自身的主题。
- 默认窗口缩小为 850×700，最小可缩至 760×600；空间不足时可滚动窗口查看内容。
- 完成圈数、模拟估算距离和运动时间移到路线、设置区域上方。
- 路线和提醒距离使用统一的扁平下拉框；速度直接输入数值，没有原生微调箭头。三个设置项及其下拉列表都不会被鼠标滚轮意外修改。
- 跑步时显示移动位置、已走路段和本圈进度。图形跟随成功发送的模拟坐标更新，并在新一圈开始时重新显示本圈进度。
- 移除左上角帮助菜单。使用、来源和开源许可说明随软件一起安装。
- 支持覆盖安装并沿用旧安装目录；升级保留默认路线的现有内容、自定义路线和用户设置。

## 安装与升级

运行 release/VRun-0.3.0-Setup-x64.exe。安装包自带 Python、Qt 和运行依赖，无需安装 Python、conda 或运行 pip。首版面向原生 Windows x64，主要在 Windows 11 上开发和验证。

安装器默认尝试准备 Apple 通信组件与 USB 驱动：已有组件会复用；缺少组件时从官方地址下载、校验签名并安装。首次准备驱动需要联网和管理员授权。驱动失败不代表应用安装失败，可查看 %ProgramData%\VRun\driver-install.log 后重新运行安装包；需要重启时安装器会提示。

升级前先点击“停止并恢复定位”并关闭 VRun，再直接运行新安装包即可。安装范围一致时（所有用户或当前用户），安装器会使用旧目录和同一个卸载入口，不要求先卸载；检测到文件仍被使用时会提示关闭相关程序，不强行终止跑步任务。升级不覆盖 routes 中已经存在的默认路线文件，也不删除自定义路线。

也可以先在 Windows“已安装的应用”中卸载旧版，再安装新版。先卸载时建议备份 routes：原本由安装器安装的默认路线会被卸载，后来添加的自定义路线通常保留。覆盖升级更适合保留修改过的默认路线。卸载 VRun 不会卸载电脑上的 Apple 驱动和通信组件。

## 开始和停止

通过 USB 连接并解锁 iPhone，确认“信任此电脑”。iOS 16 及以上还需要在“设置 → 隐私与安全性”中开启开发者模式，按手机提示重启并确认。

选择路线、输入运动速度和提醒距离，点击“开始”。速度单位为 m/s，旁边自动换算每公里配速。目标提醒提供 2 km、3 km 和自定义正数，可关闭；达标只提醒一次并继续运动。

界面只有“未运行／运行中”两种运行状态和“开始／停止并恢复定位”两个操作按钮。右上角外观选择在运行时也可切换。Windows 系统通知可能被通知设置或请勿打扰模式屏蔽，界面同时显示目标达成提示。

## 路线、可视化与统计

安装目录 routes 预置 HNroute.txt、ZJG-west.txt、ZJG-east.txt，默认东区。后两者来自原工作目录的 west_test.txt、east_test.txt。添加兼容的 UTF-8 .txt 文件后重启即可选择；向 Program Files 写入文件可能需要管理员权限。

沿用上游的坐标格式和 BD-09 坐标约定，支持 lat、lng 字典组成的列表或逗号分隔坐标。软件校验、闭合路线并转换为 WGS-84，不要直接导入已经是 WGS-84 的路线。

图中的绿色空心标记表示路线起点，移动圆点表示本次模拟位置，高亮线表示本圈已走路段；进度条和百分比随坐标更新。它是模拟运行的可视化，不是从手机读取的实时 GPS 轨迹。停止后保留最后进度，重新开始或切换路线时归零。

每完成一次完整路线循环记一圈。“模拟估算距离”按完成圈数乘以一圈长度计算，每圈更新一次；本圈动画不会提前增加统计距离，因此目标提醒可能延迟不到一圈。首次跳到起点和恢复定位不计距离。这些数值不代表其他手机应用统计的运动量。当前使用固定路线与固定速度，不实现系统步数注入。

## 异常与配置

停止时先终止坐标更新，再向本次选定的同一设备发送恢复定位命令。失败会保留提示，可再次点击“停止并恢复定位”重试。正常关闭窗口也会尝试停止和恢复；断电、USB 断开或整个程序被强杀时不保证恢复。

设备通信使用有超时的后台线程。UTF-8 主日志在 %LocalAppData%\VRun\vrun.log，iOS 17+ 组件日志在同目录 ios17-helper.log。新增组件的配对记录和镜像缓存由 pymobiledevice3 存放在当前用户的 .pymobiledevice3 目录，不会纳入源码或安装包。外观、路线、速度及提醒选择保存在当前用户的 Software\VRun\VRun 注册表项中，覆盖升级时保留。软件不会保存锁屏密码，也不会把配对记录打包进仓库。

## 开发与构建

本机可继续使用 conda base：

    conda activate base
    python -m pip install -r requirements-dev.txt
    python main.py
    python -m pytest -q
    python scripts/build.py --installer

构建需要 Windows x64、Python 3.14、Inno Setup 6/7，可用 INNO_ISCC 指定编译器。应用输出为 dist/VRun/VRun.exe，安装包在 release 中。安装目录 SOURCE 提供对应应用、独立定位组件及已归档的设备工具和新增 copyleft 依赖源码。requirements-ios17.txt 为本次验证的依赖快照，third_party/ios17-dependencies.json 记录来源和源码校验值；需要更新快照时运行 python scripts/archive_ios17.py 后重新测试。构建会先打包独立组件，再打包 GUI，检查组件的 --check 自检并复制到应用 _internal/ios17。

运行界面预览不会连接或控制手机：

    python main.py --screenshot build/preview-light.png --theme light --running-preview
    python main.py --screenshot build/preview-dark.png --theme dark --running-preview

## 来源与许可

桌面应用采用 MPL-2.0，保留上游 Git 历史；独立 ios17_helper 组件采用 GPL-3.0-or-later，使用 GPLv3+ 的 pymobiledevice3，通过标准输入输出的 JSON 行协议与桌面应用通信。第三方组件及 Wintun 预编译驱动保留各自许可，不统一改标为 MPL。来源和改动见 UPSTREAM.md；第三方组件按各自许可证分发，见 THIRD_PARTY_NOTICES.md、LICENSES 和安装目录 SOURCE。

原项目：https://github.com/iOSRealRun/iOSRealRun-cli

iOS 17+ 参考：https://github.com/iOSRealRun/iOSRealRun-cli-17

通信依赖：https://github.com/doronz88/pymobiledevice3
本项目：https://github.com/yhf216/VRun

这是本地测试版本。自动化测试和本机安装验证不代表所有 iPhone/iOS 组合都已实测；公开发布前仍需在干净 Windows 和目标真机上验收，并补齐第三方原生构建来源核对。
