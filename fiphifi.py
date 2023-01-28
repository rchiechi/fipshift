import os
import time
import logging
import threading
import queue
import urllib.request
import re
import json
from urllib.error import HTTPError, URLError
from socket import timeout as socket_timeout
from metadata import FIPMetadata

FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
FIPBASEURL = 'https://stream.radiofrance.fr'
AACRE = re.compile(f'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    def __init__(self, alive, lock, tmpdir):
        threading.Thread.__init__(self)
        self.alive = alive
        self.lock = lock
        self.buff = queue.Queue()
        self.fiphifi = FipHifi(self.alive, self.lock, self.buff, tmpdir)
        self.fiphifi.start()

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
            _urlz.append(_l)
        for _url in _urlz:
            self.buff.put(f'{FIPBASEURL}{_url}')


class FipHifi(threading.Thread):

    def __init__(self, alive, lock, queue, tmpdir):
        threading.Thread.__init__(self)
        self.alive = alive
        self.lock = lock
        self.queue = queue
        self.tmpdir = tmpdir
        self.cue = os.path.join(tmpdir, 'metdata.json')
        self.fipmeta = FIPMetadata(self.alive)

    def run(self):
        fip_error = False
        while self.alive.is_set():
            if self.queue.empty():
                time.sleep(1)
                continue
            _url = self.queue.get()
            _m = re.match(AACRE, _url)
            if _m is None:
                logger.warn("Empty URL?")
                continue
            fn = _m.groups()[0]
            req = urllib.request.urlopen(_url)
            try:
                self.handlechunk(fn, req.read())
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

    def handlechunk(self, _fn, _chunk):
        fn = os.path.join(self.tmpdir, _fn)
        with open(fn, 'wb') as fh:
            fh.write(_chunk)
        with self.lock:
            with open(self.cue, 'at') as fh:
                fh.write(f'{fn}%{self.fipmeta.slug}\n')


if __name__ == '__main__':
    alive = threading.Event()
    lock = threading.Lock()
    alive.set()
    os.mkdir('/tmp/fiptest')
    pl = FipPlaylist(alive, lock, '/tmp/fiptest')
    try:
        pl.start()
    except KeyboardInterrupt:
        alive.clear()
