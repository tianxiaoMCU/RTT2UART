# Issue #13：独立 Windows 手动部署验收回执

状态：**尚未执行，请逐项填写**。可用“通过 / 失败 / 未执行”，不要默认勾选。

| 环境项 | 实际值 |
| --- | --- |
| 验收日期、时区 | 2026/11/03 UTC+8 |
| Windows 版本、build、x64 架构 | Windows 11 专业工作站版 22H2 22621.4317 X64 |
| 物理机 / 虚拟机 | 物理机 |
| J-Link Software 包版本 / DLL 位数 | V7.52b 64bits |
| 是否已安装 Python、Qt、IDE 等开发环境 | 已安装 |
| 解压目录（不含个人账户名亦可） | C:\Users\tianxiao\Desktop\RTT2UART-issue13 |
| EXE SHA-256 与给定值一致 | 一致 |
| 本轮是否连接探针或串口设备 | 未连接；基础 GUI 验收无需连接 |

| 检查 | 结果 | 实际值或现象 / 截图文件 |
| --- | --- | --- |
| 首次启动、图标、资源、无报错 | 无报错 | |
| 测试 Target 历史及 SWD/1000 kHz/115200 载入 | 正常 | |
| USB 默认自动重连关闭 | 正常 | |
| Existing Session 默认开启、Target 控件禁用 | 正常 | |
| TCP/IP 始终禁用、切回 USB 恢复 | 正常 | |
| 编辑配置后正常关闭、重开保留选择 | 正常 | 保存前：STM32F407VG、JTAG、750 kHz、19200；COM4；勾选 Auto Reconnect 重开后： STM32F407VG、JTAG、750 kHz、19200；COM4；Auto Reconnect关闭 |
| 重开后 USB 自动重连关闭 | 正常 | |
| 选择器 Cancel 不改变 Target | 正常 | |
| 选择器空白 OK 不改变 Target | 正常 | |
| ARM7 加入历史、可选回 STM32H750VB | 正常 | |
| 第二次启动不产生第二主窗口 | 正常 | |
| 两种空闲模式正常关闭、进程退出 | 正常 | |
| last-exit-code.txt 为 0 | 正常 | |
| 最终配置恢复 STM32H750VB / SWD / 1000 kHz / 115200 | 正常 | |

截图：`01-initial.png`、`02-existing.png`、`03-reopened.png`、`04-selector.png`。

异常步骤、原始错误信息及是否可重复：待填写。

本回执不包含实机传输、两个探针排他性、原生阻塞或底层复位/暂停验收。
