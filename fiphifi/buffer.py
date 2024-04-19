import os
import time
import logging
import threading
import queue
import requests

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')
BUFFERSIZE = 10
# TSLENGTH = 4

class Buffer(threading.Thread):

    def __init__(self, _alive, urlq, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'TS Buffer Thread'
        self._alive = _alive
        self.urlq = urlq
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self._fifo = kwargs.get('fifo', os.path.join(self.tmpdir, 'fipshift.fifo'))
        self._timestamp = 0
        self._queue = queue.Queue(maxsize=BUFFERSIZE)
        self.fifo = None

    def run(self):
        logger.info('Starting Buffer')
        session = requests.Session()
        self.fifo = FIFO(self._alive, self._fifo, self._queue)
        self.fifo.start()
        try:
            while self.alive:
                try:
                    self._timestamp, _url = self.urlq.get_nowait()
                    req = session.get(_url, timeout=3)
                    _ts = os.path.join(self.tmpdir, os.path.basename(_url.split('?')[0]))
                    logger.debug('%s writing %s to %s', self.name, _url, _ts)
                    with open(_ts, 'wb') as fh:
                        fh.write(req.content)
                        logger.debug('%s wrote %s', self.name, _ts)
                    self._queue.put([self._timestamp, _ts])
                except (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout,
                        requests.exceptions.ConnectionError,
                        queue.Empty) as msg:
                    logger.warning('%s timed out fetching upstream: "%s".', self.name, str(msg))
                    time.sleep(2)
                if not self.fifo.is_alive():
                    logger.warning('%s: FIFO died, trying to restart.', self.name)
                    self.fifo = FIFO(self._alive, self._fifo, self._queue)
                    self.fifo.start()
        except Exception as msg:
            logger.error("%s died because of %s", self.name, str(msg))
            pass
        finally:
            logger.info("%s ended", self.name)

    @property
    def timestamp(self):
        return float(self._timestamp)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastsend(self):
        if self.fifo is not None:
            return self.fifo.lastsend
        else:
            return 0


class FIFO(threading.Thread):

    def __init__(self, _alive, _fifo, tsq):
        threading.Thread.__init__(self)
        self._alive = _alive
        self.tsq = tsq
        self._fifo = _fifo
        self._timestamp = 0
        self._lastsend = 0
        with open(SILENTAAC, 'rb') as fh:
            self.silence = fh.read()

    def run(self):
        logger.info('Starting FIFO')
        fifo = open(self._fifo, 'wb')
        try:
            while self.alive:
                try:
                    self._timestamp, _ts = self.tsq.get_nowait()
                    with open(_ts, 'rb') as fh:
                        fifo.write(fh.read())
                        logger.debug("FIFO sent %s", fh.name)
                    os.unlink(_ts)
                except (FileNotFoundError, queue.Empty) as msg:
                    logger.warning('FIFO sending 4s of silence after "%s".', msg)
                    fifo.write(self.silence)
                self._lastsend = time.time()
            fifo.close()
        except BrokenPipeError as msg:
            logger.error(f"FIFO died because of {msg}")
            pass
        finally:
            logger.info("FIFO ended")

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastsend(self):
        return time.time() - self._lastsend
