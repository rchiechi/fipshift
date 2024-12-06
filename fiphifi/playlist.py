import time
import logging
import threading
import json
import datetime as dt
from fiphifi.util import parsets, checkcache
from fiphifi.constants import FIPBASEURL, FIPLIST, STRPTIME, BUFFERSIZE, TSLENGTH
from fiphifi.M3U8Handler import M3U8Handler
import requests

logger = logging.getLogger(__package__+'.playlist')


class FipPlaylist(threading.Thread):

    offset = -4
    delay = 5
    duration = TSLENGTH

    def __init__(self, _alive, dlqueue, cache_file):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self._alive = _alive
        self.cache_file = cache_file
        self.dlqueue = dlqueue
        self._history, self.buff = checkcache(self.cache_file)
        self.lock = threading.Lock()
        self.last_update = time.time()
        self.idx = {0:0}

#         # Initialize handlers and queues
#         self.m3u8_handler = M3U8Handler(FIPBASEURL, self.dlqueue)
# 
#     def run(self):
#         logger.info('Starting %s', self.name)
#         if not self.alive:
#             logger.warn("%s called without alive set.", self.name)
#             
#         self.checkhistory()
#         retries = 0
#         fip_error = False
#         
#         # Calculate timezone offset
#         self.offset = time.gmtime().tm_hour - dt.datetime.now().hour
#         logger.info(f'Using offset of -{self.offset} hours in playlist')
#         
#         while self.alive:
#             try:
#                 req = requests.get(FIPLIST, timeout=self.delay)
#                 if req.ok:
#                     # Use M3U8Handler to parse playlist
#                     if self.m3u8_handler.parse_playlist(req.text):
#                         retries = 0
#                         self.last_update = time.time()
#                         # Sync our history with handler's history
#                         self._history = self.m3u8_handler.history
#                         # Write to cache periodically
#                         self.writecache()
#                         # Prune old segments
#                         self.m3u8_handler.prune_history(self.buff.qsize() + BUFFERSIZE)
#                     else:
#                         logger.warning("Failed to parse playlist")
#                         
#             except requests.exceptions.ConnectionError as error:
#                 fip_error = True
#                 logger.warning("%s: A ConnectionError has occurred: %s", self.name, error)
#             except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
#                 fip_error = True
#                 logger.warning("%s request timed out", self.name)
#             finally:
#                 if fip_error:
#                     retries += 1
#                     fip_error = False
#                     if retries > 9:
#                         logger.error("%s Maximum retries reached, dying.", self.name)
#                         self._alive.clear()
#                     else:
#                         logger.warning("%s error, retrying (%s)", self.name, retries)
#                         continue
#                 time.sleep(self.delay)
#                 
#         logger.info('%s wrote %s urls to cache', self.name, self.writecache())
#         logger.warning('%s ended (alive: %s)', self.name, self.alive)

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        self.checkhistory()
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
            if len(self._history) > self.buff.qsize():
                self.prunehistory(self.buff.qsize() - BUFFERSIZE)
        logger.info('%s wrote %s urls to cache', self.name, self.writecache())
        logger.warning('%s ended (alive: %s)', self.name, self.alive)

    def puthistory(self, _url):
        with self.lock:
            self._history.append(_url)

    def writecache(self):
        with self.lock:
            with open(self.cache_file, 'w') as fh:
                json.dump(self._history, fh)
        logger.info("%s cache: %0.0f min", self.name, len(self._history) * TSLENGTH / 60)
        return len(self._history)

    def gethistory(self):
        with self.lock:
            return self._history[:]

    def prunehistory(self, until):
        if until <= 0:
            return
        logger.debug("%s pruning history %s -> %s.", self.name, len(self._history), until)
        logger.info("%s cache: %0.0f min", self.name, len(self._history) * TSLENGTH / 60)
        with self.lock:
            self._history = self._history[-until:]
        logger.info("%s cache: %0.0f min", self.name, len(self._history) * TSLENGTH / 60)

    def checkhistory(self):
        logger.info('Loaded %s entries from cache.', self.qsize)
        prefix, suffix = 0, 0
        with self.lock:
            for _url in self._history:
                prefix, suffix = parsets(_url[1])
                if prefix in self.idx:
                    self.idx[prefix].append(suffix)
                else:
                    self.idx = {prefix: [suffix]}
        if 0 not in (prefix, suffix):
            logger.info("Bootstrapping index at %s:%s", prefix, suffix)

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
            self.ingest_url([_timestamp, f'{FIPBASEURL}{_l.strip()}'])
        if not _timestamp:
            logger.warning("%s did not parse the playlist", self.name)
        self.last_update = time.time()
        self.delay = 20

    def ingest_url(self, _url):
        prefix, suffix = parsets(_url[1])
        if 0 in (prefix, suffix):
            logger.warning('Malformed url: %s', _url[1])
            return
        if _url in self._history:
            logger.debug("%s m3u overlap %s:%s ", self.name, prefix, suffix)
            return
        if prefix in self.idx:
            _last_suffix = self.idx[prefix][-1]
            if suffix > _last_suffix:
                self.idx[prefix].append(suffix)
                if suffix - _last_suffix > 1:
                    logger.warning("%s skipped a file %s: %s -> %s", self.name, prefix, _last_suffix, suffix)
            elif suffix < _last_suffix:
                logger.debug("%s backwads url order %s: %s -> %s", self.name, prefix, _last_suffix, suffix)
                return
            elif suffix == _last_suffix:
                logger.debug("%s same url twice in a row %s: %s ", self.name, prefix, suffix)
                return
            else:
                logger.debug("%s file out of order for %s: %s -> %s", self.name, prefix, _last_suffix, suffix)
        else:
            logger.debug("%s incrementing prefix: %s", self.name, prefix)
            self.idx = {prefix: [suffix]}
        self.puthistory(_url)
        self.buff.put(_url)
        self.dlqueue.put(_url[1])
        logger.debug("%s cached %s @ %s:%s", self.name, _url[0], prefix, suffix)

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastupdate(self):
        return time.time() - self.last_update

    @property
    def history(self):
        return self.gethistory()

    @property
    def urlq(self):
        return self.buff

    @urlq.setter
    def urlq(self, _queue):
        self.buff = _queue

    @property
    def qsize(self):
        if self.buff.empty():
            return 0
        return self.buff.qsize()

    @property
    def tslength(self):
        return self.duration