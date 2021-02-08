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
    def __init__(self, connect_inf='USB', connect_para=None, device=None, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False):
        # jlink接入方式
        self._connect_inf = connect_inf
        # jlink接入参数
        self._connect_para = connect_para
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

        if self._connect_inf == 'USB':
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

        self.socket = None

        self.timer = threading.Timer(0.5, self.check_socket_status)

    def __del__(self):
        self.stop()

    def start(self):
        try:
            if self._connect_inf != 'EXISTING' and self.jlink.connected() == False:
                # 加载jlinkARM.dll
                if self._connect_inf == 'USB':
                    self.jlink.open(serial_no=self._connect_para)
                else:
                    self.jlink.open(ip_addr=self._connect_para)

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

        self.socket = self.doConnect('localhost', 19021)
        if self.socket:
            self.thread_switch = True

            self.rtt2uart = threading.Thread(target=self.rtt_to_uart)
            self.rtt2uart.setDaemon(True)
            self.rtt2uart.name = 'rtt->serial'
            self.rtt2uart.start()

            self.uart2rtt = threading.Thread(target=self.uart_to_rtt)
            self.uart2rtt.setDaemon(True)
            self.uart2rtt.name = 'serial->rtt'
            self.uart2rtt.start()
        else:
            raise Exception("Connect or config RTT server failed")

    def stop(self):
        self.thread_switch = False
        self.rtt2uart.join(0.5)
        self.uart2rtt.join(0.5)

        if self._connect_inf == 'USB':
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

                if self._connect_para == True and rtt_recv == b'':
                    self.thread_switch = False
                    self.socket.close()
                    # telnet服务器已经关闭，开启定时查询服务器状态
                    self.timer.start()

            except socket.error as msg:
                logger.error(msg, exc_info=True)
                # probably got disconnected
                raise Exception("Jlink rtt read error")

            try:
                if rtt_recv:
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

    def doConnect(self, host, port):
        socketlocal = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            socketlocal.connect((host, port))
        except socket.error:
            socketlocal.close()
            socketlocal = None
            pass
        return socketlocal

    def check_socket_status(self):
        self.timer = threading.Timer(1, self.check_socket_status)

        # 连接到RTT Telnet Server
        self.socket = self.doConnect('localhost', 19021)
        if self.socket:
            # 连接成功，重建线程
            self.thread_switch = True

            self.rtt2uart = threading.Thread(target=self.rtt_to_uart)
            self.rtt2uart.setDaemon(True)
            self.rtt2uart.name = 'rtt->serial'
            self.rtt2uart.start()

            self.uart2rtt = threading.Thread(target=self.uart_to_rtt)
            self.uart2rtt.setDaemon(True)
            self.uart2rtt.name = 'serial->rtt'
            self.uart2rtt.start()

            self.timer.cancel()
        else:
            # 连接失败，继续尝试连接
            self.timer.start()


if __name__ == "__main__":
    serial_name = input("请输入虚拟串口对中的串口名字，如COM26：")

    if '' == serial_name:
        serial_name = 'COM26'

    test = rtt_to_serial('AMAPH1KK-KBR', serial_name, 115200)
    test.start()
