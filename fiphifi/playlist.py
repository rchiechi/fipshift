import time
import logging
import threading
import re
import datetime as dt
from fiphifi.constants import FIPBASEURL, FIPLIST, TSRE, STRPTIME  # type: ignore
import requests  # type: ignore

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    delay = 5

    def __init__(self, _alive, pl_queue):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self._alive = _alive
        self.buff = pl_queue
        self._history = []
        self.lock = threading.Lock()
        self.last_update = time.time()

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        retries = 0
        fip_error = False
        while self.alive:
            try:
                req = requests.get(FIPLIST, timeout=2)
                self.parselist(req.text)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("%s: A ConnectionError has occured: %s", self.name, error)
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
                fip_error = True
                logger.warning("%s requst timed out", self.name)
            finally:
                if fip_error:
                    retries += 1
                    time.sleep(retries)
                    fip_error = False
                    if retries > 9:
                        logger.error("%s Maximum retries reached, bailing.", self.name)
                        break
                    else:
                        logger.warning("%s error, retrying (%s)", self.name, retries)
                        continue
                time.sleep(self.delay)
            if len(self._history) > self.buff.qsize():
                logger.debug("%s pruning history.", self.name)
                self.prunehistory(self.buff.qsize())
        logger.info('%s dying (alive: %s)', self.name, self.alive)

    def puthistory(self, _url):
        with self.lock:
            self._history.append(_url)

    def gethistory(self):
        with self.lock:
            return self._history[:]

    def prunehistory(self, until):
        with self.lock:
            self._history = self._history[until:]

    def parselist(self, _m3u):
        if not _m3u:
            logger.warning("%s: empty playlist.", self.name)
            self.delay = 0.5
            return
        _urlz = []
        _dt = ''
        for _l in _m3u.split('\n'):
            if not _l:
                continue
            if '#EXT-X-PROGRAM-DATE-TIME' in _l:
                _dt = ':'.join(_l.strip().split(':')[1:])
                try:
                    _dt = dt.datetime.strptime(_dt, STRPTIME) - dt.timedelta(hours=4)
                    _timestamp = _dt.timestamp()  # Fip reports timestamps four hours in the future?
                except ValueError:
                    _timestamp = 0
            if _l[0] == '#':
                continue
            _url = [_timestamp, f'{FIPBASEURL}{_l.strip()}']
            if _url not in self._history:
                _urlz.append([_timestamp, f'{FIPBASEURL}{_l.strip()}'])
                self.puthistory(_url)
                self.buff.put(_url)
        self.last_update = time.time()
        self.delay = 15

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastupdate(self):
        return time.time() - self.last_update

    @property
    def history(self):
        return self.gethistory()
