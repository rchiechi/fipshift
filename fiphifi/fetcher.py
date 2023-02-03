import os
import time
import logging
import threading
import queue
import subprocess
from tempfile import TemporaryDirectory
import re
from fiphifi.constants import AACRE
from fiphifi.metadata import FIPMetadata
import requests
from mutagen.mp3 import EasyMP3 as MP3

logger = logging.getLogger(__package__)


class FipChunks(threading.Thread):

    metamap = {}
    _empty = True
    spool = []

    def __init__(self, alive, pl_queue, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'FipChunk Thread'
        self.alive = alive
        self.urlqueue = pl_queue
        self.filequeue = kwargs.get('mp3_queue', queue.Queue())
        self._tmpdir = kwargs.get('tmpdir', TemporaryDirectory())
        self.cue = os.path.join(self.tmpdir, 'metdata.txt')
        self.ffmpeg = kwargs.get('ffmpeg', '/usr/bin/ffmpeg')
        self.fipmeta = FIPMetadata(self.alive)
        self.last_chunk = time.time()
        logging.getLogger("urllib3").setLevel(logging.WARN)

    def run(self):
        logger.info('Starting %s', self.name)
        self.fipmeta.start()
        fip_error = False
        session = requests.Session()
        while self.alive.is_set():
            if self.urlqueue.empty():
                logger.debug("%s Empy URL Queue.", self.name)
                time.sleep(5)
                session = requests.Session()
                continue
            _url = self.urlqueue.get()
            _m = re.match(AACRE, _url)
            if _m is None:
                logger.warning("Empty URL?")
                continue
            fn = _m.groups()[0]
            try:
                req = session.get(_url, timeout=10)
                self.__handlechunk(fn, req.content)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("A ConnectionError has occured: %s", error)
            except requests.exceptions.Timeout:
                logger.warning("%s timed out fetching chunk.", self.name)
                fip_error = True
            finally:
                if fip_error:
                    retries += 1
                    fip_error = False
                    if retries > 9:
                        logger.error("%s Maximum retries reached, bailing.", self.name)
                        break
                    else:
                        logger.warning("Fip playlist stream error, retrying (%s)", retries)
                        continue
        logger.info('%s dying', self.name)

    def __handlechunk(self, _fn, _chunk):
        if not self.fipmeta.is_alive():
            logger.warn("%s: Metadata thread died, restarting", self.name)
            self.fipmeta = FIPMetadata(self.alive)
            self.fipmeta.run()
        if not _chunk:
            logger.warn("%s empty chunk", self.name)
            return
        self.spool.append(_chunk)
        self.last_chunk = time.time()
        if len(self.spool) < 10:
            return
        fn = os.path.join(self.tmpdir, f'{time.time():.0f}.mp3')
        self.__ffmpeg(b''.join(self.spool), fn)
        _meta = self.fipmeta.slug
        if os.path.exists(fn):
            self.filequeue.put((fn, _meta))
        else:
            logger.error("Failed to create %s", fn)
        with open(self.cue, 'at') as fh:
            fh.write(f'{fn}%{_meta}\n')
            self.metamap[fn] = _meta
        self.spool = []
        self._empty = False

    def __ffmpeg(self, _chunk, _out):
        p = subprocess.Popen([self.ffmpeg,
                              '-i', 'pipe:',
                              '-acodec', 'libmp3lame',
                              '-b:a', '192k',
                              '-f', 'mp3',
                              '-y',
                              _out],
                             cwd=self.tmpdir,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        try:
            p.communicate(_chunk)
            p.wait(timeout=60)
            _mp3 = MP3(_out)
            _mp3['title'] = self.fipmeta.track
            _mp3['artist'] = self.fipmeta.artist
            _mp3['album'] = self.fipmeta.album
            _mp3.save()
        except subprocess.TimeoutExpired:
            logger.error("%s is stuck, skipping chunk.", self.ffmpeg)
        finally:
            self._empty = True

    @property
    def getmetadata(self, fn):
        _metamap = {}
        for _fn in self.metamap:
            if os.path.exists(_fn):
                _metamap[_fn] = self.metamap[_fn]
        self.metamap = _metamap
        return _metamap.get(fn, '')

    @property
    def tmpdir(self):
        try:
            _tmpdir = self._tmpdir.name
        except AttributeError:
            _tmpdir = self._tmpdir
        return _tmpdir

    @tmpdir.setter
    def tmpdir(self, _dir):
        if os.path.exists(_dir):
            self._tmpdir = _dir

    @property
    def empty(self):
        return self._empty

    @property
    def remains(self):
        return self.fipmeta.remains

    @property
    def lastupdate(self):
        return time.time() - self.last_chunk