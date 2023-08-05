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
        self.history = []
        self.last_update = time.time()

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        fip_error = False
        while self.alive:
            req = requests.get(FIPLIST, timeout=2)
            try:
                self.parselist(req.text)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("%s: A ConnectionError has occured: %s", self.name, error)
                self.__guess()
            except requests.exceptions.Timeout:
                logger.warning("%s requst timed out", self.name)
                self.__guess()
            finally:
                if fip_error:
                    retries += 1
                    fip_error = False
                    if retries > 9:
                        logger.error("%s Maximum retries reached, bailing.", self.name)
                        break
                    else:
                        logger.warning("%s error, retrying (%s)", self.name, retries)
                        continue
                time.sleep(self.delay)
            if len(self.history) > 1024:
                logger.debug("%s pruning history.", self.name)
                self.history = self.history[1024:]
        logger.info('%s dying (alive: %s)', self.name, self.alive)

    def __guess(self):
        logger.warn("Guessing at next TS file")
        self.delay = 5
        _last = self.history[-1]
        m = re.search(TSRE, _last)
        if m is None:
            logger.error("Error guessing : (")
            return
        if len(m.groups()) < 3:
            logger.error("Error parsing ts file")
            return
        _url, _first, _second = m.groups()[0:3]
        _i = int(_second)
        for _ in range(5):
            _i += 1
            self.buff.put(f'{FIPBASEURL}{_url}{_first}{_i}')

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
            if _l not in self.history:
                _urlz.append([_timestamp, f'{FIPBASEURL}{_l.strip()}'])
                self.history.append(_l)
        for _url in _urlz:
            self.buff.put(_url)
        # logger.debug("%s queued %s urls", self.name, len(_urlz))
        self.last_update = time.time()
        self.delay = 15

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastupdate(self):
        return time.time() - self.last_update
