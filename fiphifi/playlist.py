import time
import logging
import threading
import json
import datetime as dt
from fiphifi.util import parsets
from fiphifi.constants import FIPBASEURL, FIPLIST, STRPTIME, BUFFERSIZE
import requests

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    delay = 5
    duration = 4

    def __init__(self, _alive, pl_queue, cache_file, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self._alive = _alive
        self.buff = pl_queue
        self._history = kwargs.get('history', [])
        self.cache_file = cache_file
        self.cached = [[0,0]]
        self.lock = threading.Lock()
        self.last_update = time.time()
        self.offset = 0

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        retries = 0
        fip_error = False
        #  Fip reports timestamps in GMT
        #  which is five hours in the future during EST
        #  and four hours during EDT
        self.offset = time.gmtime().tm_hour - dt.datetime.now().hour
        logger.info(f'Using offset of -{self.offset} hours in playlist')
        while self.alive:
            try:
                req = requests.get(FIPLIST, timeout=self.delay)
                self.parselist(req.text)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("%s: A ConnectionError has occured: %s", self.name, error)
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
                fip_error = True
                logger.warning("%s requst timed out", self.name)
            finally:
                self.writecache()
                if fip_error:
                    retries += 1
                    fip_error = False
                    if retries > 9:
                        logger.error("%s Maximum retries reached, dying.", self.name)
                        self.alive.clear()
                    else:
                        logger.warning("%s error, retrying (%s)", self.name, retries)
                        continue
                time.sleep(self.delay)
            if len(self._history) > self.buff.qsize() + BUFFERSIZE:
                logger.debug("%s pruning history.", self.name)
                self.prunehistory(self.buff.qsize() + BUFFERSIZE)
        logger.info('%s wrote %s urls to cache', self.name, self.writecache())
        logger.info('%s ended (alive: %s)', self.name, self.alive)

    def puthistory(self, _url):
        with self.lock:
            self._history.append(_url)

    def writecache(self):
        with open(self.cache_file, 'w') as fh:
            json.dump(self._history, fh)
        logger.debug("%s cache size: %s", self.name, len(self._history))
        return len(self._history)

    def gethistory(self):
        with self.lock:
            return self._history[:]

    def prunehistory(self, until):
        with self.lock:
            self._history = self._history[until:]
            if until < len(self.cached):
                self.cached = self.cached[until:]

    def parselist(self, _m3u):
        if not _m3u:
            logger.warning("%s: empty playlist.", self.name)
            self.delay = 0.5
            return
        _timestamp = 0
        for _l in _m3u.split('\n'):
            if not _l:
                continue
            if '#EXT-X-PROGRAM-DATE-TIME' in _l:
                _dt = ':'.join(_l.strip().split(':')[1:])
                try:
                    _dt = dt.datetime.strptime(_dt, STRPTIME) - dt.timedelta(hours=self.offset)
                    _timestamp = _dt.timestamp()
                except ValueError:
                    _timestamp = 0
            if '#EXT-X-TARGETDURATION' in _l:
                try:
                    self.duration = int(_l.strip().split(':')[-1])
                except (IndexError, ValueError):
                    logger.warning("Error finding duration from %s", _l.strip())
            if _l[0] == '#':
                continue
            _url = [_timestamp, f'{FIPBASEURL}{_l.strip()}']
            self._cache_url(_url)
        self.last_update = time.time()
        self.delay = 15

    def _cache_url(self, _url):
        tsid = parsets(_url[1])
        if tsid == [0,0]:
            logger.warning('Malformed url: %s', _url[1])
            return
        if tsid in self.cached:
            return
        if tsid[1] != self.cached[-1][1] + 1 and self.cached[-1][0] > 0:
            if tsid[1] < self.cached[-1][1]:
                logger.warning('Refusing to cache backwards: %s -> %s', self.cached[-1], tsid)
                return
            else:
                logger.warning('Playlist out of order: %s -> %s', self.cached[-1], tsid)
        self.cached.append(tsid)
        self.puthistory(_url)
        self.buff.put(_url)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastupdate(self):
        return time.time() - self.last_update

    @property
    def history(self):
        return self.gethistory()
