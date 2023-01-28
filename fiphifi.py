import time
import logging
import threading
import queue
import urllib.request
from urllib.error import HTTPError, URLError
from socket import timeout as socket_timeout

FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
FIPBASEURL = 'https://stream.radiofrance.fr'
# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    buff = []

    def __init__(self, alive):
        threading.Thread.__init__(self)
        self.alive = alive
        self.buff = queue.Queue()

    def run(self):
        fip_error = False
        while self.alive.is_set():
            req = urllib.request.urlopen(FIPLIST)
            time.sleep(1)
            try:
                self.parselist(req.read())
                retries = 0
            except URLError as error:
                fip_error = True
                logger.warning("A URLError has occured: %s", error)
            except HTTPError as error:
                fip_error = True
                logger.warning("An HTTPerror has occured: %s", error)
            except socket_timeout as error:
                fip_error = True
                logger.warning("Socket timeout: %s", error)
            if fip_error:
                retries += 1
                fip_error = False
                if retries > 9:
                    logger.error("Maximum retries reached, bailing.")
                    print("\n%s: emtpy block after %s retries, dying.\n" % (retries, self.getName()))
                    logger.error("%s: emtpy block after %s retries, dying.", retries, self.getName())
                    self.alive.clear()
                    break
                else:
                    logger.warning("Fip playlist stream error, retrying (%s)", retries)
                    continue

    def parselist(self, _m3u):
        if not _m3u:
            return
        _urlz = []
        for _l in str(_m3u, encoding='utf8').split('\n'):
            if not _l:
                continue
            if _l[0] == '#':
                continue
            if _l not in _urlz:
                _urlz.append(_l)
        for _url in _urlz:
            print(f'{FIPBASEURL}{_url}')
            self.buff.put(f'{FIPBASEURL}{_url}')


if __name__ == '__main__':
    alive = threading.Event()
    alive.set()
    pl = FipPlaylist(alive)
    pl.start()
