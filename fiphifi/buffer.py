import os
import time
import logging
import threading
import queue
import requests
import psutil
import shutil
import subprocess
from fiphifi.util import parsets
from fiphifi.constants import BUFFERSIZE, TSLENGTH

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')


class Buffer(threading.Thread):

    def __init__(self, _alive, urlq, playlist, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'Buffer Thread'
        self._alive = _alive
        self.urlq = urlq
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self._timestamp = [[0, time.time()]]
        self.last_timestamp = 0
        self.playlist = playlist

    def run(self):
        logger.info('Starting Buffer')
        session = requests.Session()
        try:
            while self.alive:
                self.playlist.next()
                if self.playlist.buffersize > BUFFERSIZE:
                    time.sleep(1)
                    continue
                try:
                    _timestamp, _url = self.urlq.get(timeout=TSLENGTH)
                    req = self._get_url(session, _url)
                    if req is None:
                        logger.warning("%s failed to fetch %s", self.name, _url)
                        continue
                    _ts = os.path.join(self.tmpdir, os.path.basename(_url.split('?')[0]))
                    with open(_ts, 'wb') as fh:
                        fh.write(req.content)
                        logger.debug('%s wrote %s', self.name, _ts)
                    self.playlist.add(_ts)
                    self._timestamp.append([parsets(_ts)[1], _timestamp])
                except queue.Empty:
                    logger.warning('%s url queue empty.', self.name)
                    time.sleep(TSLENGTH)
        except Exception as msg:
            logger.error("%s died %s", self.name, str(msg))
        finally:
            self.playlist.cleanup()
            logger.info('%s exiting.', self.name)

    def _get_url(self, session, url):
        for _i in range(2, 4):
            try:
                return session.get(url, timeout=TSLENGTH * BUFFERSIZE / _i)
            except (requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError):
                pass
        return None

    @property
    def timestamp(self):
        _timestamp = self.last_timestamp
        for _i, _item in enumerate(self._timestamp):
            if _item[0] == self.playlist.nowplaying:
                _timestamp = _item[1]
                self.last_timestamp = _timestamp
                self._timestamp = self._timestamp[_i:]
                break
        return _timestamp

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def initialized(self):
        return self.playlist.initialized

class Playlist():

    def __init__(self, ffmpeg_cmd, **kwargs):
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self.playlist = os.path.join(self.tmpdir, 'playlist.txt')
        self.tsfiles = (os.path.join(self.tmpdir, "first.ts"),
                        os.path.join(self.tmpdir, "second.ts"))
        self.ffmpeg_cmd = ffmpeg_cmd
        self.ffmpeg_proc = None
        self.tsqueue = queue.SimpleQueue()
        self.current = {-1: 0, 0: 0, 1: 0}
        self._lastupdate = 0
        self.last_pls = -1
        self.initialized = False
        if not os.path.exists(self.playlist):
            self._create_playlist()

    def _create_playlist(self):
        with open(self.playlist, 'w') as fh:
            fh.write('ffconcat version 1.0\n')
            fh.write(f"file '{self.tsfiles[0]}'\n")
            fh.write(f"file '{self.tsfiles[1]}'\n")
        logger.info("Created %s", self.playlist)

    def _update(self, _src, _i):
        _ts = self.tsfiles[_i]
        # fd = os.open(_ts, os.O_CREAT | os.O_WRONLY | os.O_NONBLOCK)
        # with os.fdopen(fd) as f:
        #     with open(_src) as sf:
        #         shutil.copyfileobj(sf, f)
        try:
            # shutil.move(_src, _ts)
            with open(_src) as src_fh:
                with open(_ts, 'w') as dst_fh:
                    dst_fh.write(src_fh.read())
            os.unlink(_src)
            self.current[_i] = parsets(_src)[1]
            self._lastupdate = time.time()
            logger.debug("Playlist 0: %s, 1: %s", self.current[0], self.current[1])
        except FileNotFoundError:
            logger.error("%s does not exist, cannot add to playlist", _src)

    def _init_ffmpeg(self):
        if self.ffmpeg_alive:
            logger.debug("ffmpeg already running, not initializing.")
            return
        logger.info('Starting ffmpeg')
        if self.initialized and not self.ffmpeg_healthy:
            self._advance_playlist(force=True)
        self.ffmpeg_proc = subprocess.Popen(self.ffmpeg_cmd,
                                            stdin=subprocess.PIPE,
                                            stdout=open(os.path.join(self.tmpdir, 'ffmpeg.log'), 'w'),
                                            stderr=subprocess.STDOUT)
        time.sleep(1)
        if not self.ffmpeg_alive:
            logger.error("Failed to start ffmpeg")

    def _get_ffmpeg_proc(self):
        if not self.ffmpeg_alive:
            self._init_ffmpeg()
        if self.ffmpeg_alive:
            try:
                return psutil.Process(self.ffmpeg_pid)
            except psutil.NoSuchProcess as msg:
                logger.warning("Error updating playlist: %s", msg)
        return None

    def _init_playlist(self):
        if self.tsqueue.qsize() < len(self.tsfiles):
            logger.info("Playlist waiting for queue to fill before initializing.")
            return
        if self.initialized:
            return
        for _i, _ts in enumerate(self.tsfiles):
            _src = self.tsqueue.get()
            self._update(_src, _i)
        self._init_ffmpeg()
        self.initialized = True
        self._get_playing()

    def _advance_playlist(self, force=False):
        if not self.initialized:
            logger.debug("Not advancing playlist until initialized.")
            self._init_playlist()
            return -1
        if self.tsqueue.qsize() > BUFFERSIZE:
            logger.debug("Playlist length %s > buffersize %s.", self.tsqueue.qsize(), BUFFERSIZE)
        if self.tsqueue.empty():
            logger.warning("Can't advance playlist when queue is empty.")
            return -1
        if force and self.tsqueue.qsize() >= len(self.tsfiles):
            logger.info("Forcing playlist update")
            for _i, _ts in enumerate(self.tsfiles):
                _src = self.tsqueue.get()
                self._update(_src, _i)
                return -1
        #  Check to see which idx is playing
        #  and then make sure the next idx is
        #  larger than the current one
        playing = self._get_playing()
        if playing == 0:
            # logger.debug("Checking if %s > %s", self.current[0], self.current[1])
            #  If we are playing idx 0 and it is larger than idx 1
            #  we have to update idx 1 to the next item in the queue
            if self.current[0] > self.current[1]:
                _src = self.tsqueue.get()
                self._update(_src, 1)
        elif playing == 1:
            # logger.debug("Checking if %s > %s", self.current[1], self.current[0])
            #  If we are playing idx 1 and it is larger than idx 0
            #  we have to update idx 0 to the next item in the queue
            if self.current[1] > self.current[0]:
                _src = self.tsqueue.get()
                self._update(_src, 0)
        else:
            logger.warning("Playlist in unknown state %s", playing)
        return playing

    def _get_playing(self):
        if self.lastupdate > TSLENGTH+1 and self.lastupdate < 1000:
            logger.warning("Playlist updated more than %ss ago (%0.0f)", TSLENGTH, self.lastupdate)
        if 1000 > self.lastupdate > 300:
            logger.warning("It's been more than 5 minutes, dying.")
            raise OSError("Playlist neglected!")
        proc = self._get_ffmpeg_proc()
        if proc is None:
            return -1
        try:
            for item in proc.open_files():
                for _i, _ts in enumerate(self.tsfiles):
                    if os.path.basename(item.path) == os.path.basename(_ts):
                        self.last_pls = _i
                        return _i
        except psutil.ZombieProcess:
            logger.error("FFMPEG is a zombie process!")
        logger.warning("Playlist could not determine what ffmpeg is currently playing.")
        return -1

    def add(self, tsfile):
        logger.debug("Playlist queued %s", os.path.basename(tsfile))
        self.tsqueue.put(tsfile)
        self._advance_playlist()

    def next(self):
        self._advance_playlist()

    def cleanup(self):
        if self.ffmpeg_alive:
            self.ffmpeg_proc.terminate()
            time.sleep(1)
            if self.ffmpeg_alive:
                self.ffmpeg_proc.kill()
        try:
            os.unlink(self.playlist)
        except FileNotFoundError:
            pass

    @property
    def lastupdate(self):
        return time.time() - self._lastupdate

    @property
    def nowplaying(self):
        return self.current[self._advance_playlist()]

    @property
    def buffersize(self):
        #  The real buffer should be BUFFERSIZE - 1 because the playlist is two items long
        return self.tsqueue.qsize() + 1

    @property
    def ffmpeg_pid(self):
        if self.ffmpeg_alive:
            return self.ffmpeg_proc.pid
        return None

    @property
    def ffmpeg_alive(self):
        if self.ffmpeg_proc is None:
            return False
        if self.ffmpeg_proc.poll() is None:
            return True
        return False

    @property
    def ffmpeg_healthy(self):
        if self.ffmpeg_alive or self.ffmpeg_proc is None:
            return True
        if self.ffmpeg_proc.poll() == 0:
            return True
        return False

