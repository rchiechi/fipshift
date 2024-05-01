import time
import logging
import threading
import queue
from fiphifi.buffer import Buffer
from fiphifi.constants import TSLENGTH


logger = logging.getLogger(__package__+'.sender')

class AACStream(threading.Thread):

    playing = False
    session = None
    buffer = None
    duration = TSLENGTH

    def __init__(self, _alive, urlqueue, delay, config, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'AAC Sender Thread'
        self._alive = _alive
        self.urlq = urlqueue
        self._delay = delay
        self.config = config
        self._timestamp = 0

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        buffer_alive = threading.Event()
        buffer_alive.set()
        self.buffer = Buffer(buffer_alive,
                             self.urlq,
                             config=self.config)
        self.buffer.start()
        offset_tolerace = int(0.1 * self.delay) or 16
        logger.debug('Setting offset tolerance to %ss', offset_tolerace)
        while self.alive:
            if not self.buffer.is_alive() and self.alive:
                logger.warning('Buffer died, trying to restart.')
                self.buffer = Buffer(buffer_alive,
                                     self.urlq,
                                     config=self.config)
                self.buffer.start()
            if offset_tolerace < self.delta < 100000:  # Offset throws huge numbers when timestamp returns 0
                logger.info('Offset: %0.0f / Delay: %0.0f / Tolerance: %0.0f / Diff: %0.0f',
                            self.offset, self.delay, offset_tolerace, self.delta - offset_tolerace)
                skipped = 1
                try:
                    _timestamp, _ = self.urlq.get(timeout=5)
                    while time.time() - _timestamp > self.delay:
                        _timestamp, _ = self.urlq.get(timeout=5)
                        skipped += 1
                except queue.Empty:
                    pass
                logger.info("Sskipped %s urls to keep delay.", skipped)
                logger.debug('Offset: %0.0f / Delay: %0.0f', self.offset, self.delay)
            time.sleep(self.duration)
        logger.warning('%s dying (alive: %s)', self.name, self.alive)
        buffer_alive.clear()
        self._cleanup()

    def _cleanup(self):
        self.playing = False
        if self.buffer is not None:
            self.buffer.join(30)
            if self.buffer.is_alive():
                logger.warning("%s refusing to die.", self.buffer.name)
        logger.warning('%s ending.', self.name)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def timestamp(self):
        if self.buffer is not None:
            return float(self.buffer.timestamp)
        else:
            return 0

    @property
    def offset(self):
        return time.time() - self.timestamp

    @property
    def delta(self):
        return self.offset - self.delay

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, _delay):
        if isinstance(_delay, int):
            self._delay = _delay

    @property
    def tslength(self):
        return self.duration

    @tslength.setter
    def tslength(self, _duration):
        if _duration > 0:
            self.duration = _duration
        else:
            logger.error("%s not setting tslength < 0")