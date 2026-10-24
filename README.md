# VRun

Windows 桌面虚拟跑步与定位模拟工具。基于 iOSRealRun/iOSRealRun-cli，首版面向 iOS 15–16，iOS 17 及以上不支持。

## 使用

安装 VRun 后打开桌面或开始菜单中的 VRun。安装包自带 Python、Qt 和运行依赖，无需配置 Python、conda 或 pip。

安装器默认尝试准备 Apple 通信组件与 USB 驱动：已有组件会复用；缺少组件时从官方地址下载、校验签名并安装。首次安装需要联网和管理员授权。驱动准备失败不代表应用安装失败，可查看 %ProgramData%\VRun\driver-install.log 并重新运行安装包。需要重启时安装器会提示。

通过 USB 连接并解锁 iPhone，确认“信任此电脑”。iOS 16 设备还需要在“设置 → 隐私与安全性”中开启开发者模式，并按手机提示重启和确认。选择路线、速度和提醒距离后点击“开始”；点击“停止并恢复定位”结束。

首版只有“未运行／运行中”两种运行状态。目标提醒提供 2 km、3 km 和自定义正数，达到后仅提醒一次并继续运行。Windows 通知可能被系统设置或请勿打扰模式屏蔽，界面同时保留目标达成提示。

## 路线与统计

安装目录 routes 中预置 HNroute.txt、ZJG-west.txt 和 ZJG-east.txt，默认东区。后两者来自原工作目录的 west_test.txt、east_test.txt。添加兼容的 UTF-8 .txt 文件后重启软件即可选择；安装在 Program Files 时添加文件可能需要管理员权限。升级不覆盖已有默认路线文件。

沿用上游的坐标文件格式和 BD-09 坐标约定。支持由 lat、lng 字典构成的列表或逗号分隔坐标。软件会校验坐标，闭合首尾并转换为 WGS-84。不要直接导入已经是 WGS-84 的路线。

每完成一次完整路线循环记一圈；“模拟估算距离”按圈数乘以路线一圈长度计算，每圈更新一次，因此目标提醒可能延迟不到一圈。不代表其他手机应用统计的距离或真实运动量。初版使用固定速度与固定路线，不实现系统步数注入。

## 停止与异常

停止时先终止坐标更新，再向本次选定的同一设备发送恢复定位命令。恢复失败会保留提示，并可再次点击“停止并恢复定位”重试。正常关闭窗口也会尝试停止和恢复；断电、USB 断开、整个程序被强杀时不保证恢复。首次跳到起点和恢复定位不计入距离。

设备命令有超时，挂载和运行使用后台线程。日志为 UTF-8，位于 %LocalAppData%\VRun\vrun.log。程序不会收集或保存锁屏密码；不会把配对记录打包进仓库。

## 开发与构建

本机可以继续使用 conda base：

    conda activate base
    python -m pip install -r requirements-dev.txt
    python main.py
    python -m pytest -q
    python scripts/build.py --installer

构建需 Windows x64、Python 3.10–3.15 和 Inno Setup 6/7；可用 INNO_ISCC 指定编译器。PyInstaller 输出 dist/VRun/VRun.exe，安装包输出 release/VRun-0.1.0-Setup-x64.exe。安装目录 SOURCE 提供本次应用对应源码与已归档的设备工具源码。发布前应在没有 Python 的干净 Windows 系统上验收。

界面离屏预览：

    python main.py --screenshot build/preview.png

## 来源与许可

应用及修改采用 MPL-2.0。完整继承上游 Git 历史，来源、提交和改动范围见 UPSTREAM.md。第三方设备工具和 Qt 等按各自许可证分发，见 THIRD_PARTY_NOTICES.md 和 LICENSES。

原项目：https://github.com/iOSRealRun/iOSRealRun-cli
本项目：https://github.com/yhf216/VRun

当前为 0.1.0 本地初版：自动化测试不等于所有 iPhone/iOS 组合已通过实测，也不保证特定第三方应用接受模拟定位。
