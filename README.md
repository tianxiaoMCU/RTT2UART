# RTT2UART

***Note: Installed a virtual serial port tool like [com0com](http://com0com.sourceforge.net/) before use this tool !***

![VirtualSerialPort.png](./picture/VirtualSerialPort.png)

## How to use

* Step1: selete the device and click *OK*

   ![RTT2UART.png](./picture/RTT2UART.png)![SeleteDevice.png](./picture/SeleteDevice.png)
* Step2: config the target interface and speed
* Step3: tick the *Reset target* option will reset the target once connected
* Step4: scan then selete the ***virtual COM port*** like *com4* and baud rate
* Step5: click start to connect the target
* Step6: selete another com port of the com port pair like *com5*
![serialcomtool.png](./picture/serialcomtool.png)

## Update the device lists

if can't find the device you want, follow the picture below and replace the ***JLinkDevicesBuildIn.xml*** file in the path of this tool.

![exportdevicelist.png](./picture/exportdevicelist.png)

## Package the program with pyinstaller

Open *cmd.exe* in the project path and input follow command `pyinstaller -F -w -i ./swap_horiz_16px.ico main_window.py`

## 开发
### 生成UI python class
在终端中执行以下命令
```
pyside6-uic .\rtt2uart.ui -o .\ui_rtt2uart.py
pyside6-uic .\sel_device.ui -o .\ui_sel_device.py
```
### 生成资源文件python class
在终端中执行以下命令
```
pyside6-rcc .\icons.qrc -o .\rc_icons.py
```
