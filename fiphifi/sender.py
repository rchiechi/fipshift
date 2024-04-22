import os
import sys
import time
import logging
import threading
import subprocess
import queue
# import requests
from .buffer import Buffer

# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')

class AACStream(threading.Thread):

    playing = False
    session = None
    buffer = None

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
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        buffer_alive = threading.Event()
        buffer_alive.set()
        self.buffer = Buffer(buffer_alive, self.urlq, fifo=self._fifo, tmpdir=self.tmpdir)
        self.buffer.start()
        logger.info('%s starting ffmpeg', self.name)
        ffmpeg_fh = open(os.path.join(self.tmpdir, 'ffmpeg.log'), 'w')
        ffmpeg_proc = self._startstream(ffmpeg_fh)
        offset_tolerace = int(0.1 * self.delay) or 16
        logger.debug('%s setting offset tolerance to %ss', self.name, offset_tolerace)
        while self.alive:
            if not self.buffer.is_alive() and self.alive:
                logger.warning('%s Buffer died, trying to restart.', self.name)
                self.buffer = Buffer(self._alive, self.urlq, fifo=self._fifo, tmpdir=self.tmpdir)
                self.buffer.start()
            if ffmpeg_proc.poll() is not None:
                logger.warning('%s ffmpeg died, trying to restart.', self.name)
                self.playing = False
                ffmpeg_proc = self._startstream(ffmpeg_fh)
            if offset_tolerace < self.delta < 100000:  # Offset throws huge numbers when timestamp returns 0
                logger.info('Offset: %0.0f / Delay: %0.0f / Tolerance: %0.0f / Diff: %0.0f',
                            self.offset, self.delay, offset_tolerace, offset_tolerace - self.delta)
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
                logger.debug('Offset: %0.0f / Delay: %0.0f', self.offset, self.delay)
            time.sleep(1)
        logger.info('%s dying (alive: %s)', self.name, self.alive)
        buffer_alive.clear()
        ffmpeg_proc.terminate()
        time.sleep(3)
        ffmpeg_proc.kill()
        ffmpeg_fh.close()
        self._cleanup()

    def _cleanup(self):
        self.playing = False
        if self.buffer is not None:
            self.buffer.join(30)
            if self.buffer.is_alive():
                logger.warning("%s refusing to die.", self.buffer.name)
        logger.info('%s exiting.', self.name)

    def _startstream(self, fh):
        for _i in range(60, -1, -1):
            if os.path.exists(self._fifo):
                break
            time.sleep(1)
            logger.debug('%s waiting %ss for %s to be created.', self.name, _i, self._fifo)
            if _i < 1:
                logger.error("%s does not exist!", self._fifo)
                sys.exit()
        self.playing = True
        _ffmpegcmd = [self.ffmpeg,
                      '-loglevel', 'warning',
                      '-nostdin',
                      '-re',
                      '-i', self._fifo,
                      '-content_type', 'audio/aac',
                      '-ice_name', 'FipShift',
                      '-ice_description', 'Time-shifted FIP stream',
                      '-ice_genre', 'Eclectic',
                      '-c:a', 'copy',
                      '-f', 'adts',
                      f'icecast://{self.un}:{self.pw}@{self._iceserver}/{self.mount}']
        return subprocess.Popen(_ffmpegcmd, stdin=subprocess.PIPE, stdout=fh, stderr=subprocess.STDOUT)

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
    def iceserver(self):
        return self._iceserver

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, _delay):
        if isinstance(_delay, int):
            self._delay = _delay
