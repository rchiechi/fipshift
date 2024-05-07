import os
import time
import logging
import threading
import queue
import subprocess
import requests
import psutil
from fiphifi.util import parsets, get_tmpdir
from fiphifi.constants import BUFFERSIZE, TSLENGTH

logger = logging.getLogger(__package__+'.buffer')
SILENTAAC2 = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_2s.ts')
SILENTAAC4 = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_2s.ts')


def delayedstream(_c, playlist):
    _ffmpegcmd = [_c['FFMPEG'],
                  '-loglevel', 'warning',
                  '-nostdin',
                  '-re',
                  '-stream_loop', '-1',
                  '-safe', '0',
                  '-i', playlist,
                  '-f', '-concat',
                  '-flush_packets', '0',
                  '-content_type', 'audio/aac',
                  '-ice_name', 'FipShift',
                  '-ice_description', 'Time-shifted FIP stream',
                  '-ice_genre', 'Eclectic',
                  '-c', 'copy',
                  '-f', 'adts',
                  f"icecast://{_c['USER']}:{_c['PASSWORD']}@{_c['HOST']}:{_c['PORT']}/{_c['MOUNT']}"]
    return subprocess.Popen(_ffmpegcmd,
                            stdin=subprocess.PIPE,
                            stdout=open(os.path.join(get_tmpdir(_c), 'ffmpeg.log'), 'w'),
                            stderr=subprocess.STDOUT)

class Buffer(threading.Thread):

    duration = TSLENGTH

    def __init__(self, _alive, urlq, config):
        threading.Thread.__init__(self)
        self.name = 'Buffer Thread'
        self._alive = _alive
        self.urlq = urlq
        self.dldir = os.path.join(get_tmpdir(config['USEROPTS']), 'ts')
        self._timestamp = [[0, time.time()]]
        self.last_timestamp = 0
        self.playlist = Playlist(config)
        with open(SILENTAAC4, 'rb') as fh:
            self.lastts = fh.read()

    def run(self):
        logger.info('Starting Buffer')
        session = requests.Session()
        try:
            while self.alive:
                if not self.advance(session):
                    session = requests.Session()
        except Exception as msg:
            logger.error("%s died %s", self.name, str(msg))
        finally:
            self.playlist.cleanup()
            logger.warning('%s ending.', self.name)

    def advance(self, session):
        self.playlist.next()
        if self.playlist.buffersize > BUFFERSIZE:
            time.sleep(0.5)
            return True
        success = False
        try:
            _timestamp, _url = self.urlq.get(timeout=self.duration)
            _ts = os.path.join(self.dldir, os.path.basename(_url.split('?')[0]))
            if os.path.exists(_ts):
                success = True
            _retry_start = time.time()
            while not success:
                if time.time() - _retry_start >= self.duration * BUFFERSIZE:
                    logger.warning("%s could not download %s", self.name, os.path.basename(_url))
                    break
                req = self._get_url(session, _url)
                if req is not None:
                    if not req.ok:
                        logger.warning("%s bad url %s", self.name, _url)
                        break
                    with open(_ts, 'wb') as fh:
                        fh.write(req.content)
                    if os.path.getsize(_ts) > 4096:
                        logger.debug('%s wrote %s (%0.0f kb)', self.name, _ts, os.path.getsize(_ts) / 1024)
                        with open(_ts, 'rb') as fh:
                            self.lastts = fh.read()
                        success = True
                    else:
                        logger.debug("%s req: %s", self.name, req.content)
                        logger.warning("%s %s empty, retrying", self.name, os.path.basename(_url))
                        time.sleep(1)
            if not success:
                logger.warning("%s inserting garbage for %s", self.name, _ts)
                with open(_ts, 'wb') as fh:
                    fh.write(self.lastts)
            self.playlist.add(_ts)
            self._timestamp.append([parsets(_ts)[1], _timestamp])
        except queue.Empty:
            logger.warning('%s url queue empty.', self.name)
            time.sleep(self.duration)
        return success

    def _get_url(self, session, url):
        req = None
        for _i in range(3, 30, 3):
            try:
                req = session.get(url, timeout=self.duration)
                if req is not None:
                    if req.ok:
                        return req
                    elif req.status_code == 404:
                        logger.error("%s not found", url)
                        return None
                    else:
                        logger.warning("Got response code: %s", req.status_code)
                        time.sleep(_i)
            except (requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError):
                pass
            logger.warning("Retrying %s", url)
        return req

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

    @property
    def tslength(self):
        return self.duration

    @tslength.setter
    def tslength(self, _duration):
        if _duration > 0:
            self.duration = _duration
        else:
            logger.error("%s not setting tslength < 0", self.name)

class Playlist():

    duration = TSLENGTH

    def __init__(self, config):
        self.config = config
        self.dldir = os.path.join(get_tmpdir(self.config['USEROPTS']), 'ts')
        self.playlist = os.path.join(self.dldir, 'playlist.txt')
        self.tsfiles = ("first.ts", "second.ts")
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
        if os.path.exists(self.playlist):
            logger.info("Created %s", self.playlist)
        else:
            logger.error("Could not create %s", self.playlist)
            raise OSError(f"Could not create {self.playlist}")

    def _update(self, _src, _i):
        _ts = os.path.join(self.dldir, self.tsfiles[_i])
        try:
            if os.path.getsize(_src) == 0:
                logger.warning("Refusing to write empty file %s.", _src)
            else:
                os.replace(_src, _ts)
            logger.debug("%s: %0.0f kb", _ts, os.path.getsize(_ts) / 1024)
            self.current[_i] = parsets(_src)[1]
            self._lastupdate = time.time()
            logger.info("Playlist 0: %s, 1: %s", self.current[0], self.current[1])
        except (OSError, FileNotFoundError):
            logger.error("Error reading %s, cannot add to playlist", _src)

    def _init_ffmpeg(self):
        if self.ffmpeg_alive:
            logger.debug("ffmpeg already running, not initializing.")
            return
        logger.info('Starting ffmpeg')
        if self.initialized and not self.ffmpeg_healthy:
            self._advance_playlist(force=True)
        self.ffmpeg_proc = delayedstream(self.config['USEROPTS'], self.playlist)
        time.sleep(1)
        if not self.ffmpeg_alive:
            logger.error("Failed to start ffmpeg")

    def _get_ffmpeg_proc(self):
        if not self.ffmpeg_alive:
            logger.debug("ffmpeg is not alive, calling init_ffmpeg")
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
        # if force and self.tsqueue.qsize() >= len(self.tsfiles):
        if force:
            logger.info("Forcing update")
            playing = 0
            self.current[0] = self.current[1] + 1
        #  Check to see which idx is playing
        #  and then make sure the next idx is
        #  larger than the current one
        else:
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
        return playing

    def _get_playing(self):
        if self.lastupdate > self.duration+1 and self.lastupdate < 1000:
            logger.warning("Playlist updated more than %ss ago (%0.0f)", self.duration, self.lastupdate)
        if 1000 > self.lastupdate > 60:
            logger.warning("It's been more than a minute, dying.")
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
        if self.ffmpeg_proc.returncode == 0:
            logger.debug("ffmpeg returned: %s", self.ffmpeg_proc.returncode)
            return True
        return False

    @property
    def tslength(self):
        return self.duration

    @tslength.setter
    def tslength(self, _duration):
        if _duration > 0:
            self.duration = _duration
        else:
            logger.error("Playlist not setting tslength < 0")
