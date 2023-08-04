import os
# import sys
import time
import logging
import threading
# import queue
import subprocess
# import re
import requests  # type: ignore

# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)

class FIFO(threading.Thread):

    def __init__(self, alive, urlqueue, tmpdir):
        threading.Thread.__init__(self)
        self.alive = alive
        self.urlq = urlqueue
        self._fifo = os.path.join(tmpdir, 'fipshift.fifo')
        self._timestamp = 0

    def run(self):
        logger.info('Starting FIFO')
        os.mkfifo(self._fifo)
        fifo = open(self._fifo, 'wb')
        session = requests.Session()
        while self.alive.isSet():
            self._timestamp, _url = self.urlq.get()
            req = session.get(_url, timeout=1)
            fifo.write(req.content)
        fifo.close()
        os.unlink(self._fifo)
        logger.info("FIFO ended")

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def pipe(self):
        return self._fifo

class AACStream(threading.Thread):

    playing = False
    fifo = None

    def __init__(self, alive, urlqueue, delay, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'AAC Sender Thread'
        self._alive = alive
        self.urlq = urlqueue
        self._delay = delay
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self.ffmpeg = kwargs.get('ffmpeg', '/usr/bin/ffmpeg')
        _server = kwargs.get('server', 'localhost')
        _port = kwargs.get('port', '8000')
        self.mount = kwargs.get('mount', 'fipshift')
        self._iceserver = f'{_server}:{_port}'
        _auth = kwargs.get('auth', ['', ''])
        self.pw = _auth[1]
        # self.auth = requests.auth.HTTPBasicAuth(_auth[0], _auth[1])
        self._timesamp = 0

    def run(self):
        logger.info('Starting %s', self.name)
        self.fifo = FIFO(self._alive, self.urlq, self.tmpdir)
        self.fifo.start()
        _ffmpegcmd = [self.ffmpeg,
                      '-loglevel', 'fatal',
                      '-re',
                      '-i', self.fifo.pipe,
                      '-c:a', 'copy',
                      '-f', 'adts',
                      f'icecast://source:{self.pw}@{self._iceserver}/{self.mount}']
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        while self.alive:
            # self._timestamp, _url = self.urlq.get()
            logger.info('%s buffering for 30 seconds', self.name)
            time.sleep(30)
            logger.info('%s starting ffmpeg', self.name)
            _p = subprocess.run(_ffmpegcmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if _p.stdout:
                logger.error(str(_p.stdout, encoding='utf-8'))
            # logger.debug('Offset: %s / Delay: %s', self.offset, self.delay)
        logger.info('%s dying (alive: %s)', self.name, self.alive)
        self.fifo.join()

    @property
    def alive(self):
        return self._alive.isSet()

    @alive.setter
    def alive(self, _bool):
        if not _bool:
            self._alive.clear()
        else:
            self._alive.set()

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
