import os
import time
import logging
import threading
import subprocess
import queue
import requests  # type: ignore

# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')

class FIFO(threading.Thread):

    def __init__(self, _alive, _fifo, urlq):
        threading.Thread.__init__(self)
        self._alive = _alive
        self.urlq = urlq
        self._fifo = _fifo
        self._timestamp = 0
        self._lastsend = 0
        with open(SILENTAAC, 'rb') as fh:
            self.silence = fh.read()

    def run(self):
        logger.info('Starting FIFO')

        fifo = open(self._fifo, 'wb')
        session = requests.Session()
        try:
            while self.alive:
                try:
                    self._timestamp, _url = self.urlq.get_nowait()
                    req = session.get(_url, timeout=1)
                    fifo.write(req.content)
                except (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout,
                        requests.exceptions.ConnectionError,
                        queue.Empty) as msg:
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
    def timestamp(self):
        return self._timestamp

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastsend(self):
        return time.time() - self._lastsend


class AACStream(threading.Thread):

    playing = False
    fifo = None
    session = None

    def __init__(self, _alive, urlqueue, delay, config, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'AAC Sender Thread'
        self._alive = _alive
        self.urlq = urlqueue
        self._delay = delay
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self.ffmpeg = config['USEROPTS']['FFMPEG']
        self.mount = config['USEROPTS']['MOUNT']
        self._iceserver = f"{config['USEROPTS']['HOST']}:{config['USEROPTS']['PORT']}"
        self.un = config['USEROPTS']['USER']
        self.pw = config['USEROPTS']['PASSWORD']
        self._fifo = os.path.join(self.tmpdir, 'fipshift.fifo')
        self._timestamp = 0

    def run(self):
        logger.info('Starting %s', self.name)
        self._cleanup()
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        logger.info('Creating %s', self._fifo)
        os.mkfifo(self._fifo)
        logger.debug('Opening %s', self._fifo)
        self.fifo = FIFO(self._alive, self._fifo, self.urlq)
        self.fifo.start()
        logger.info('%s starting ffmpeg', self.name)
        ffmpeg_proc = self._startstream()
        offset_tolerace = int(0.05 * self.delay) or 16
        logger.debug('%s setting offset tolerance to %ss', self.name, offset_tolerace)
        while self.alive:
            if not self.fifo.is_alive():
                logger.warning('%s FIFO died, trying to restart.', self.name)
                self.fifo = FIFO(self._alive, self._fifo, self.urlq)
                self.fifo.start()
            if ffmpeg_proc.poll() is not None:
                logger.warning('%s ffmpeg died, trying to restart.', self.name)
                self.playing = False
                ffmpeg_proc = self._startstream()
            if offset_tolerace < self.delta < 100000:  # Offset throws huge numbers when timestamp returns 0
                logger.info('Offset: %0.0f / Delay: %0.0f', self.offset, self.delay)
                skipped = 1
                try:
                    _timestamp, _ = self.urlq.get(timeout=5)
                    while time.time() - _timestamp > self.delay:
                        _timestamp, _ = self.urlq.get(timeout=5)
                        skipped += 1
                except queue.Empty:
                    pass
                logger.info("%s skipped %s urls to keep delay.", self.name, skipped)
                time.sleep(8)
                while self.fifo.lastsend > 1:
                    logger.debug('%s waiting 1s for fifo to catch up.', self.name)
                    time.sleep(1)
                logger.debug('Offset: %0.0f / Delay: %0.0f', self.offset, self.delay)
            time.sleep(1)
        logger.info('%s dying (alive: %s)', self.name, self.alive)
        self._cleanup()

    def _cleanup(self):
        self.playing = False
        if os.path.exists(self._fifo):
            os.unlink(self._fifo)

    def _startstream(self):
        time.sleep(1)
        self.playing = True
        _ffmpegcmd = [self.ffmpeg,
                      '-loglevel', 'fatal',
                      '-re',
                      '-i', self._fifo,
                      '-content_type', 'audio/aac',
                      '-ice_name', 'FipShift',
                      '-ice_description', 'Time-shifted FIP stream',
                      '-ice_genre', 'Eclectic',
                      '-c:a', 'copy',
                      '-f', 'adts',
                      f'icecast://{self.un}:{self.pw}@{self._iceserver}/{self.mount}']
        return subprocess.Popen(_ffmpegcmd)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def timestamp(self):
        if self.fifo is not None:
            return float(self.fifo.timestamp)
        else:
            return 0

    @property
    def offset(self):
        return time.time() - self.timestamp

    @property
    def delta(self):
        return self.offset - self.delay

    @property
    def iceserver(self):
        return self._iceserver

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, _delay):
        if isinstance(_delay, int):
            self._delay = _delay
