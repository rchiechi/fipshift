import os
import sys
import time
import logging
import threading
import queue
import requests
from .constants import BUFFERSIZE, TSLENGTH

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')


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
        fifo_alive = threading.Event()
        fifo_alive.set()
        self.fifo = FIFO(fifo_alive, self._fifo, self._queue)
        self.fifo.start()
        try:
            while self.alive:
                try:
                    self._timestamp, _url = self.urlq.get(timeout=TSLENGTH)
                    req = session.get(_url, timeout=TSLENGTH)
                    _ts = os.path.join(self.tmpdir, os.path.basename(_url.split('?')[0]))
                    logger.debug('%s writing %s to %s', self.name, _url, _ts)
                    with open(_ts, 'wb') as fh:
                        fh.write(req.content)
                        logger.debug('%s wrote %s', self.name, _ts)
                    self._queue.put([self._timestamp, _ts], timeout=30)
                except (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout,
                        requests.exceptions.ConnectionError,
                        ):
                    logger.warning('%s timed out fetching upstream url %s.', self.name, _url)
                    time.sleep(2)
                except queue.Empty:
                    logger.warning('%s url queue empty.', self.name)
                if not self.fifo.is_alive() and self.alive:
                    logger.warning('%s: FIFO died, trying to restart.', self.name)
                    self.fifo = FIFO(fifo_alive, self._fifo, self._queue)
                    self.fifo.start()
        except Exception as msg:
            logger.error("%s died %s", self.name, str(msg))
            pass
        finally:
            fifo_alive.clear()
            self._cleanup()

    def _cleanup(self):
        self.fifo.join(10)
        if self.fifo.is_alive():
            logger.warning("%s could not kill FIFO thread", self.name)
        logger.info('%s exiting.', self.name)

    @property
    def timestamp(self):
        return float(self._timestamp - (TSLENGTH * BUFFERSIZE))

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
        self.history = []
        with open(SILENTAAC, 'rb') as fh:
            self.silence = fh.read()

    def run(self):
        logger.info('Starting FIFO')
        if os.path.exists(self._fifo):
            logger.info('Removing stale %s', self._fifo)
            os.unlink(self._fifo)
        logger.info('Creating %s', self._fifo)
        os.mkfifo(self._fifo)
        logger.debug('Opening %s', self._fifo)
        fifo = open(self._fifo, 'wb')
        try:
            while self.alive:
                if not os.path.exists(self._fifo):
                    logger.warning('FIFO: %s does not exist', self._fifo)
                    sys.exit()
                try:
                    self._timestamp, _ts = self.tsq.get_nowait()
                    if _ts in self.history:
                        logger.debug('Not sending duplicate %s', os.path.basename(_ts))
                        continue
                    with open(_ts, 'rb') as fh:
                        fifo.write(fh.read())
                        logger.debug("FIFO sent %s", fh.name)
                    os.unlink(_ts)
                    self._add_to_history(_ts)
                except (FileNotFoundError) as msg:
                    logger.warning('FIFO error opening %s, sending 4s of silence.', msg)
                    fifo.write(self.silence)
                except queue.Empty:
                    logger.debug('FIFO file queue empty, waiting %ss.', TSLENGTH)
                    time.sleep(TSLENGTH)
                self._lastsend = time.time()
            logger.info("FIFO dying")
            fifo.close()
        except BrokenPipeError as msg:
            if self.alive:
                logger.error(f"FIFO died because of {msg}")
            pass
        finally:
            if os.path.exists(self._fifo):
                os.unlink(self._fifo)
            logger.info("FIFO ended")

    def _add_to_history(self, _ts):
        if len(self.history) > 2 * BUFFERSIZE:
            self.history = self.history[2 * BUFFERSIZE:]
        self.history.append(_ts)
        if len(self.history) < 2:
            return
        try:
            _last = int(_ts.split("_")[-1].split('.')[0])
            _prior = int(self.history[-2].split("_")[-1].split('.')[0])
        except (ValueError, IndexError):
            logger.debug("FIFO: error finding sequence of %s", _ts)
            return False
        if _last - _prior != 1:
            logger.warn("FIFO: sent files out of order: %s -> %s", _prior, _last)

    @property
    def alive(self):
        return self._alive.isSet()

