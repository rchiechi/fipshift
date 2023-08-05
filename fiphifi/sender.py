import os
import time
import logging
import threading
import subprocess
import requests  # type: ignore

# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class FIFO(threading.Thread):

    def __init__(self, _alive, _fifo, urlq):
        threading.Thread.__init__(self)
        self._alive = _alive
        self.urlq = urlq
        self._fifo = _fifo
        self._timestamp = 0

    def run(self):
        logger.info('Starting FIFO')
        fifo = open(self._fifo, 'wb')
        session = requests.Session()
        try:
            while self.alive:
                self._timestamp, _url = self.urlq.get()
                req = session.get(_url, timeout=1)
                fifo.write(req.content)
        except BrokenPipeError:
            pass
        finally:
            fifo.close()
            logger.info("FIFO ended")

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def pipe(self):
        return self._fifo

    @property
    def alive(self):
        return self._alive.isSet()


class AACStream(threading.Thread):

    playing = False
    fifo = None
    session = None

    def __init__(self, _alive, urlqueue, delay, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'AAC Sender Thread'
        self._alive = _alive
        self.urlq = urlqueue
        self._delay = delay
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self._fifo = os.path.join(self.tmpdir, 'fipshift.fifo')
        self.ffmpeg = kwargs.get('ffmpeg', '/usr/bin/ffmpeg')
        _server = kwargs.get('host', 'localhost')
        _port = kwargs.get('port', '8000')
        self.mount = kwargs.get('mount', 'fipshift')
        self._iceserver = f'{_server}:{_port}'
        _auth = kwargs.get('auth', ['', ''])
        self.pw = _auth[1]
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
        try:
            while self.alive:
                self._writechunk()
                if ffmpeg_proc.poll() is not None:
                    self.playing = False
                    ffmpeg_proc = self._startstream()
                logger.debug('Offset: %s / Delay: %s', self.offset, self.delay)
            logger.info('%s dying (alive: %s)', self.name, self.alive)
            self.fifo.close()
        except BrokenPipeError:
            pass
        finally:
            self.playing = False
            self._cleanup()

    def _cleanup(self):
        if os.path.exists(self._fifo):
            os.unlink(self._fifo)

    def _startstream(self):
        time.sleep(1)
        self.playing = True
        _ffmpegcmd = [self.ffmpeg,
                      '-loglevel', 'fatal',
                      '-re',
                      '-i', self.fifo.pipe,
                      '-content_type', 'audio/aac',
                      '-ice_name', 'FipShift',
                      '-ice_description', 'Time-shifted FIP stream',
                      '-ice_genre', 'Eclectic',
                      '-c:a', 'copy',
                      '-f', 'adts',
                      f'icecast://source:{self.pw}@{self._iceserver}/{self.mount}']
        return subprocess.run(_ffmpegcmd)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def timestamp(self):
        if self.fifo is not None:
            return self.fifo.timestamp
        else:
            return 0

    @property
    def offset(self):
        return time.time() - self.timestamp

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
