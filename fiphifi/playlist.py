import time
import logging
import threading
import re
from fiphifi.constants import FIPBASEURL, FIPLIST, TSRE
import requests

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    def __init__(self, alive, pl_queue):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self.alive = alive
        self.buff = pl_queue
        self.history = []

    def run(self):
        logger.info('Starting %s', self.name)
        fip_error = False
        session = requests.Session()
        while self.alive.is_set():
            req = session.get(FIPLIST, timeout=2)
            time.sleep(2)
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
            if len(self.history) > 1024:
                logger.debug("%s pruning history.", self.name)
                self.history = self.history[1024:]

        logger.info('%s dying', self.name)

    def __guess(self):
        logger.warn("Guessing at next TS file")
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
            return
        _urlz = []
        for _l in _m3u.split('\n'):
            if not _l:
                continue
            if _l[0] == '#':
                continue
            if _l not in self.history:
                _urlz.append(_l)
                self.history.append(_l)
        for _url in _urlz:
            self.buff.put(f'{FIPBASEURL}{_url}')