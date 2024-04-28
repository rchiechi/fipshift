import os
import time
import logging
import threading
import queue
from fiphifi.buffer import Buffer, Playlist
from fiphifi.constants import TSLENGTH

# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)

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
        self.ffmpeg_pidfile = os.path.join(self.tmpdir, 'ffmpeg.pid')
        self.mount = config['USEROPTS']['MOUNT']
        self.iceserver = f"{config['USEROPTS']['HOST']}:{config['USEROPTS']['PORT']}"
        self.un = config['USEROPTS']['USER']
        self.pw = config['USEROPTS']['PASSWORD']
        self._playlist = os.path.join(self.tmpdir, 'playlist.txt')
        self._timestamp = 0

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        buffer_alive = threading.Event()
        buffer_alive.set()
        playlist = self._get_playlist()
        self.buffer = Buffer(buffer_alive,
                             self.urlq,
                             playlist=playlist,
                             tmpdir=self.tmpdir)
        self.buffer.start()
        offset_tolerace = int(0.1 * self.delay) or 16
        logger.debug('%s setting offset tolerance to %ss', self.name, offset_tolerace)
        while self.alive:
            if not self.buffer.is_alive() and self.alive:
                logger.warning('%s Buffer died, trying to restart.', self.name)
                self.buffer = Buffer(buffer_alive,
                                     self.urlq,
                                     playlist=playlist,
                                     tmpdir=self.tmpdir)
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
                logger.info("%s skipped %s urls to keep delay.", self.name, skipped)
                logger.debug('Offset: %0.0f / Delay: %0.0f', self.offset, self.delay)
            time.sleep(TSLENGTH)
        logger.info('%s dying (alive: %s)', self.name, self.alive)
        buffer_alive.clear()
        playlist.cleanup()
        self._cleanup()

    def _cleanup(self):
        self.playing = False
        if self.buffer is not None:
            self.buffer.join(30)
            if self.buffer.is_alive():
                logger.warning("%s refusing to die.", self.buffer.name)
        logger.info('%s exiting.', self.name)

    def _get_playlist(self):
        #  self._playlist must be an absolute path
        ffmpegcmd = [self.ffmpeg,
                     '-loglevel', 'warning',
                     '-nostdin',
                     '-re',
                     '-stream_loop', '-1',
                     '-safe', '0',
                     '-i', self._playlist,
                     '-f', '-concat',
                     '-flush_packets', '0',
                     '-content_type', 'audio/aac',
                     '-ice_name', 'FipShift',
                     '-ice_description', 'Time-shifted FIP stream',
                     '-ice_genre', 'Eclectic',
                     '-c', 'copy',
                     '-f', 'adts',
                     f'icecast://{self.un}:{self.pw}@{self.iceserver}/{self.mount}']
        return Playlist(ffmpegcmd, tmpdir=self.tmpdir)

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
