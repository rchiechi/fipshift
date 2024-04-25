import os
import time
import logging
import threading
import queue
import requests
import psutil
import shutil
from fiphifi.util import parsets
from fiphifi.constants import BUFFERSIZE, TSLENGTH

logger = logging.getLogger(__package__)
SILENTAAC = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'silence_4s.ts')


class Buffer(threading.Thread):

    def __init__(self, _alive, urlq, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'TS Buffer Thread'
        self._alive = _alive
        self.urlq = urlq
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self._timestamp = [[0, time.time()]]
        self.last_timestamp = 0
        self.playlist = Playlist(tmpdir=self.tmpdir,
                                 playlist=kwargs.get('playlist',
                                                     os.path.join(self.tmpdir, 'playlist.txt')),
                                 ffmpeg_pidfile=kwargs.get('ffmpeg_pidfile',
                                                           os.path.join(self.tmpdir, 'ffmpeg.pid')))

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
                    req = session.get(_url, timeout=TSLENGTH)
                    _ts = os.path.join(self.tmpdir, os.path.basename(_url.split('?')[0]))
                    logger.debug('%s writing %s to %s', self.name, _url, _ts)
                    with open(_ts, 'wb') as fh:
                        fh.write(req.content)
                        logger.debug('%s wrote %s', self.name, _ts)
                    self.playlist.add(_ts)
                    self._timestamp.append([parsets(_ts)[1], _timestamp])
                except (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout,
                        requests.exceptions.ConnectionError,
                        ):
                    logger.warning('%s timed out fetching upstream url %s.', self.name, _url)
                    time.sleep(2)
                except queue.Empty:
                    logger.warning('%s url queue empty.', self.name)
        except Exception as msg:
            logger.error("%s died %s", self.name, str(msg))
            logger.debug("_ts: %s, _url: %s", _ts, _url)
        finally:
            logger.info('%s exiting.', self.name)

    @property
    def timestamp(self):
        _timestamp = self.last_timestamp
        for _i, _item in enumerate(self._timestamp):
            if _item[0] == self.playlist.nowplaying:
                _timestamp = _item[1]
                self.last_timestamp = _timestamp
                self._timestamp = self._timestamp[_i:]
                # logger.debug("%s found timestamp in playlist", self.name)
                break
        return _timestamp

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def initialized(self):
        return self.playlist.initialized

class Playlist():

    def __init__(self, **kwargs):
        self.tmpdir = kwargs.get('tmpdir', '/tmp')
        self.playlist = kwargs.get('playlist', os.path.join(self.tmpdir, 'playlist.txt'))
        self.ffmpeg_pidfile = kwargs.get('ffmpeg_pidfile', os.path.join(self.tmpdir, 'ffmpeg.pid'))
        self.tsfiles = (os.path.join(self.tmpdir, "first.ts"),
                        os.path.join(self.tmpdir, "second.ts"))
        self.tsqueue = queue.SimpleQueue()
        self.current = {-1: 0, 0: 0, 1: 0}
        self._lastupdate = 0
        self.last_pls = -1
        self.initialized = False
        with open(self.playlist, 'w') as fh:
            fh.write('ffconcat version 1.0\n')
            fh.write(f'file {self.tsfiles[0]}\n')
            fh.write(f'file {self.tsfiles[1]}\n')
        logger.debug("Created %s", self.playlist)

    def _update(self, _src, _i):
        _ts = self.tsfiles[_i]
        shutil.move(_src, _ts)
        self.current[_i] = parsets(_src)[1]
        self._lastupdate = time.time()
        logger.debug("Moved %s -> %s", os.path.basename(_src), os.path.basename(_ts))
        logger.debug("0: %s, 1: %s", self.current[0], self.current[1])

    def _get_ffmpeg_proc(self):
        try:
            with open(self.ffmpeg_pidfile) as fh:
                _pid = int(fh.read().strip())
                return psutil.Process(_pid)
        except (psutil.NoSuchProcess, ValueError) as msg:
            logger.warning("Error updating playlist: %s", msg)
        except FileNotFoundError:
            logger.warning("Cannot query ffmpeg because %s does not exist", self.ffmpeg_pidfile)
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
        self.initialized = True
        self._get_playing()

    def _advance_playlist(self):
        force = False
        if not self.initialized:
            logger.debug("Not advancing playlist until initialized.")
            self._init_playlist()
        if self.tsqueue.qsize() > BUFFERSIZE:
            logger.debug("Playlist length %s > buffersize %s.", self.tsqueue.qsize(), BUFFERSIZE)
            # force = True
        #  Check to see which idx is playing
        #  and then make sure the next idx is
        #  larger than the current one
        playing = self._get_playing()
        if playing == 0:
            # logger.debug("Checking if %s > %s", self.current[0], self.current[1])
            #  If we are playing idx 0 and it is larger than idx 1
            #  we have to update idx 1 to the next item in the queue
            if self.current[0] > self.current[1] or force:
                _src = self.tsqueue.get()
                self._update(_src, 1)
        elif playing == 1:
            # logger.debug("Checking if %s > %s", self.current[1], self.current[0])
            #  If we are playing idx 1 and it is larger than idx 0
            #  we have to update idx 0 to the next item in the queue
            if self.current[1] > self.current[0] or force:
                _src = self.tsqueue.get()
                self._update(_src, 0)
        else:
            logger.warning("Playlist in unknown state %s", playing)
        return playing

    def _get_playing(self):
        if self.lastupdate > TSLENGTH+1:
            logger.warning("Playlist updated more than %ss ago (%0.0f)", TSLENGTH, self.lastupdate)
        proc = self._get_ffmpeg_proc()
        if proc is None:
            return -1
        for item in proc.open_files():
            for _i, _ts in enumerate(self.tsfiles):
                if os.path.basename(item.path) == os.path.basename(_ts):
                    self.last_pls = _i
                    return _i
        logger.warning("Playlist could not determine what ffmpeg is currently playing.")
        return -1

    def add(self, tsfile):
        logger.debug("Playlist queued %s", os.path.basename(tsfile))
        self.tsqueue.put(tsfile)
        self._advance_playlist()

    def next(self):
        self._advance_playlist()

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

