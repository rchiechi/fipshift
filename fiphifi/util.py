import os
import logging
import threading

logger = logging.getLogger(__package__)


def cleantmpdir(tmpdir):
    n = 0
    for root, __, files in os.walk(tmpdir):
        for _f in files:
            # if _f[-3:] in ('.ts', '.mp3', '.aac') or _f == 'spool.bin':
            os.remove(os.path.join(root, _f))
            n += 1
    return n


def killbuffer(signum, frame):  # pylint: disable=unused-argument
    logger.info("Received %s, dying.", signum)
    for _thread in threading.enumerate():
        if _thread != threading.main_thread():
            _thread.alive = False
    for _thread in threading.enumerate():
        if _thread != threading.main_thread():
            _thread.join()


def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins


class RestartTimeout(Exception):
    def __init__(self, expression, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(expression)
        # Now for your custom code...
        self.errors = message
