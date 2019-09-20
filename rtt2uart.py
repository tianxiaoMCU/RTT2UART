import logging
import pylink
import time
import serial

logging.basicConfig(level=logging.NOTSET,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)


class RTT2UART():
    def __init__(self, device):
        # 目标芯片名字
        self.device = device

        # segger rtt上下通道缓存大小
        self.upbuffer_size = 1024
        self.downbuffer_size = 512

        try:
            self.jlink = pylink.JLink()
        except:
            logger.error('Find jlink dll failed', exc_info=True)

    def __del__(self):
        self.jlink.close()

    def start(self):
        try:
            if self.jlink.connected() == False:
                # 加载jlinkARM.dll
                self.jlink.open()
                # 设置连接接口为SWD
                if self.jlink.set_tif(pylink.enums.JLinkInterfaces.SWD) == False:
                    logger.error('Set interface failed', exc_info=True)
                else:
                    try:
                        # 连接目标芯片
                        self.jlink.connect(self.device)
                        # 启动RTT，对于RTT的任何操作都需要在RTT启动后进行
                        self.jlink.rtt_start()
                    except pylink.errors.JLinkException:
                        logger.error('Connect target failed', exc_info=True)
                        pass
                # 复位一下目标芯片，复位后不要停止芯片，保证后续操作的稳定性
                self.jlink.reset(halt=False)
        except pylink.errors.JLinkException as errors:
            logger.error('Open jlink failed', exc_info=True)

    def stop(self):
        try:
            if self.jlink.connected() == True:
                # 使用完后停止RTT
                self.jlink.rtt_stop()
                # 释放之前加载的jlinkARM.dll
                self.jlink.close()
        except pylink.errors.JLinkException:
            logger.error('Disconnect target failed', exc_info=True)
            pass


if __name__ == "__main__":
    test = RTT2UART('AMAPH1KK-KBR')
    test.start()
    test.stop()
