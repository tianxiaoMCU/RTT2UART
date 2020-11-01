import logging
import pylink
import time
import serial
import threading
import socket

logging.basicConfig(level=logging.NOTSET,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)


class rtt_to_serial():
    def __init__(self, device, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False):
        # 目标芯片名字
        self.device = device
        # 调试口
        self._interface = interface
        # 连接速率
        self._speed = speed
        # 复位标志
        self._reset = reset

        # 串口参数
        self.port = port
        self.baudrate = baudrate

        # 线程
        self._write_lock = threading.Lock()

        try:
            self.jlink = pylink.JLink()
        except:
            logger.error('Find jlink dll failed', exc_info=True)
            raise

        try:
            self.serial = serial.Serial()
        except:
            logger.error('Creat serial object failed', exc_info=True)
            raise

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __del__(self):
        self.stop()

    def start(self):
        try:
            if self.jlink.connected() == False:
                # 加载jlinkARM.dll
                self.jlink.open()

                # 设置连接速率
                if self.jlink.set_speed(self._speed) == False:
                    logger.error('Set speed failed', exc_info=True)
                    raise Exception("Set jlink speed failed")

                # 设置连接接口为SWD
                if self.jlink.set_tif(self._interface) == False:
                    logger.error('Set interface failed', exc_info=True)
                    raise Exception("Set jlink interface failed")

                try:
                    if self._reset == True:
                        # 复位一下目标芯片，复位后不要停止芯片，保证后续操作的稳定性
                        self.jlink.reset(halt=False)

                    # 连接目标芯片
                    self.jlink.connect(self.device)
                except pylink.errors.JLinkException:
                    logger.error('Connect target failed', exc_info=True)
                    raise

                try:
                    # 连接到RTT Telnet Server
                    self.socket.connect(('localhost', 19021))

                    # 配置RTT
                    '''
                    After establishing a connection via TELNET, the user has 100ms to send a SEGGER TELNET Config String from the host system (e.g. via J-Link RTT Client or putty).
                    Sending a SEGGER TELNET config string after 100ms have passed since the TELNET connection was established has no effect and is treated the same as if it was RTT data sent from the host.
                    Additionally, sending a SEGGER TELNET config string is optional, meaning that RTT will function correctly even without sending such a config string.
                    '''
                except socket.error as msg:
                    logger.error(msg, exc_info=True)
                    raise Exception("Connect or config RTT server failed")

        except pylink.errors.JLinkException as errors:
            logger.error('Open jlink failed', exc_info=True)
            raise

        try:
            if self.serial.isOpen() == False:
                # 设置串口参数并打开串口
                self.serial.port = self.port
                self.serial.baudrate = self.baudrate
                self.serial.timeout = 3
                self.serial.write_timeout = 3
                self.serial.open()
        except:
            logger.error('Open serial failed', exc_info=True)
            raise

        self.thread_switch = True
        self.rtt2uart = threading.Thread(target=self.rtt_to_uart)
        self.rtt2uart.setDaemon(True)
        self.rtt2uart.name = 'rtt->serial'
        self.rtt2uart.start()

        self.uart2rtt = threading.Thread(target=self.uart_to_rtt)
        self.uart2rtt.setDaemon(True)
        self.uart2rtt.name = 'serial->rtt'
        self.uart2rtt.start()

    def stop(self):
        self.thread_switch = False

        try:
            if self.jlink.connected() == True:
                # 使用完后停止RTT
                self.jlink.rtt_stop()
                # 释放之前加载的jlinkARM.dll
                self.jlink.close()
        except pylink.errors.JLinkException:
            logger.error('Disconnect target failed', exc_info=True)
            pass

        try:
            if self.serial.isOpen() == True:
                self.serial.close()
        except:
            logger.error('Close serial failed', exc_info=True)
            pass

        self.socket.close()

    def rtt_to_uart(self):
        while self.thread_switch == True:
            try:
                rtt_recv = self.socket.recv(1024)
            except socket.error as msg:
                logger.error(msg, exc_info=True)
                # probably got disconnected
                raise Exception("Jlink rtt read error")

            try:
                self.serial.write(rtt_recv)
            except:
                raise Exception("Serial write error")

    def uart_to_rtt(self):
        while self.thread_switch == True:
            try:
                data = self.serial.read(self.serial.in_waiting or 1)

                if data:
                    with self._write_lock:
                        self.socket.sendall(data)
            except socket.error as msg:
                logger.error(msg, exc_info=True)
                # probably got disconnected
                raise Exception("Jlink rtt write error")


if __name__ == "__main__":
    serial_name = input("请输入虚拟串口对中的串口名字，如COM26：")

    if '' == serial_name:
        serial_name = 'COM26'

    test = rtt_to_serial('AMAPH1KK-KBR', serial_name, 115200)
    test.start()
