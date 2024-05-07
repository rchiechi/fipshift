import os
import time
import logging
import threading
import requests
from fiphifi.util import get_tmpdir

logger = logging.getLogger(__package__+'.downloader')


class Downloader(threading.Thread):

    def __init__(self, _alive, dlqueue, config):
        threading.Thread.__init__(self)
        self._alive = _alive
        self.dldir = os.path.join(get_tmpdir(config['USEROPTS']), 'ts')
        self.dlqueue = dlqueue
        if not os.path.exists(self.dldir):
            os.mkdir(self.dldir)
        self.session = requests.Session()

    def run(self):
        while self.alive:
            if not self.dlqueue.empty():
                self.dl(self.dlqueue.get())
            else:
                time.sleep(1)
        logger.warning("Downloader thread ended.")

    def dl(self, url):
        req = self._get_url(url)
        if req is None:
            return False
        if not req.ok:
            logger.warning("Bad url %s", url)
            return False
        _ts = os.path.join(self.dldir, os.path.basename(url.split('?')[0]))
        with open(_ts, 'wb') as fh:
            fh.write(req.content)
        if os.path.getsize(_ts) > 4096:
            logger.debug('Wrote %s (%0.0f kb)', _ts, os.path.getsize(_ts) / 1024)
            with open(_ts, 'rb') as fh:
                self.lastts = fh.read()
            return True

    def _get_url(self, url):
        req = None
        for _i in range(3, 30, 3):
            try:
                req = self.session.get(url)
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
    def alive(self):
        return self._alive.isSet()
