import threading
import time
import requests
import logging
from urllib3.exceptions import ReadTimeoutError
from fiphifi.constants import METAURL, METATEMPLATE

logger = logging.getLogger(__package__)


class FIPMetadata(threading.Thread):

    _newtrack = False
    metadata = METATEMPLATE
    metaurl = METAURL

    def __init__(self, _alive):
        threading.Thread.__init__(self)
        self.name = 'Metadata Thread'
        self._alive = _alive
        self.last_update = time.time()

    def run(self):
        logger.info(f"Starting {self.name}")
        self.endtime = time.time() + 10
        while self.alive:
            time.sleep(0.25)
            if time.time() - self.last_update > 300:
                logger.debug('%s: Forcing update.', self.name)
            elif self.remains > 0:
                continue
            self.__updatemetadata(requests.Session())
            time.sleep(3)

        logger.info(f"{self.name} dying")

    def __updatemetadata(self, session):
        self.__nexttonow()
        self.last_update = time.time()
        self._newtrack = True
        try:
            logger.debug("%s: Fetching metadata from Fip", self.name)
            r = session.get(self.metaurl, timeout=5)
            _json = r.json()
            if _json.get('now', {'endTime':None})['endTime'] is None:
                time.sleep(1)
                self.__updatemetadata(session)
            else:
                self.metadata = _json
        except requests.exceptions.JSONDecodeError:
            logger.error("JSON error fetching metadata from Fip.")
            self.endtime = time.time() + 10
            pass
        except requests.ReadTimeout:
            logger.error("%s: GET request timed out.", self.name)
            pass
        if self.metadata is None:
            self.metadata = METATEMPLATE
            self.endtime = time.time() + 10
            logger.error("Error fetching metadata from Fip.")
        for _k in METATEMPLATE['now']:
            if _k not in self.metadata['now']:
                self.metadata['now'][_k] = METATEMPLATE['now'][_k]
                logger.debug('%s key mangled in update', _k)

    def __nexttonow(self):
        _next = self.metadata.get('next', {"startTime": time.time()+10})['startTime']
        if _next is None:
            return
        if time.time() > _next:
            logger.debug("%s: now -> next", self.name)
            logger.debug("Before: %s", self.slug)
            self.metadata['now'] = self.metadata['next']
            logger.debug("After: %s", self.slug)

    def _getmeta(self, when):
        try:
            track = self.metadata[when]['firstLine']['title']
        except TypeError:
            track = 'Le track'
        try:
            artist = self.metadata[when]['secondLine']['title']
        except TypeError:
            artist = 'Le artist'
        try:
            album = self.metadata[when]['song']['release']['title']
        except TypeError:
            album = 'Le album'
        try:
            year = self.metadata[when]['song']['year']
        except TypeError:
            year = '1789'
        try:
            coverart = self.metadata[when]['visuals']['card']['src']
        except TypeError:
            coverart = 'https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/250x250_visual-fip.jpg'
        try:
            endtime = float(self.metadata[when]['endTime'])
        except TypeError:
            endtime = time.time()
        except ValueError:
            endtime = time.time()
        try:
            starttime = float(self.metadata[when]['startTime'])
        except TypeError:
            starttime = time.time()
        except ValueError:
            starttime = time.time()
        try:
            refresh = float(self.metadata['delayToRefresh']) / 1000
        except TypeError:
            refresh = 0
        except ValueError:
            refresh = 0
        return {
            'track': track,
            'artist': artist,
            'album': album,
            'year': year,
            'coverart': coverart,
            'endTime': endtime,
            'startTime': starttime,
            'delayToRefresh': refresh
        }

    @property
    def alive(self):
        return self._alive.isSet()

    @alive.setter
    def alive(self, _bool):
        if not _bool:
            self._alive.clear()
        else:
            self._alive.set()

    def getcurrent(self):
        return self._getmeta('now')

    @property
    def track(self):
        return self.getcurrent()['track']

    @property
    def artist(self):
        return self.getcurrent()['artist']

    @property
    def album(self):
        return self.getcurrent()['album']

    @property
    def year(self):
        return self.getcurrent()['year']

    @property
    def coverart(self):
        return self.getcurrent()['coverart']

    @property
    def slug(self):
        if self.album == 'Le album':
            return f'{self.track} - {self.artist}'
        return f'{self.track} - {self.artist} - {self.album}'

    @property
    def newtrack(self):
        if self._newtrack:
            self._newtrack = False
            return True
        return False

    @property
    def remains(self):
        _remains = self.endtime - time.time()
        if _remains < 0:
            _remains = 0
        return _remains

    @property
    def duration(self):
        _duration = self.endtime - self.starttime
        if _duration < 0:
            _duration = 0
        return _duration

    @property
    def starttime(self):
        return self.getcurrent()['startTime']

    @property
    def endtime(self):
        return self.getcurrent()['endTime']

    @endtime.setter
    def endtime(self, _time):
        self.metadata['now']['endTime'] = _time

    @property
    def lastupdate(self):
        return time.time() - self.last_update

    @property
    def refresh(self):
        _refresh = self.getcurrent()['delayToRefresh'] - self.lastupdate
        if _refresh < 0:
            _refresh = 0
        return _refresh

# Metadata channel

# GET /admin/metadata?pass=hackme&mode=updinfo&mount=/mp3test&song=Even%20more%20meta%21%21 HTTP/1.0
# Authorization: Basic c291cmNlOmhhY2ttZQ==
# User-Agent: (Mozilla Compatible)


if __name__ == '__main__':
    import sys
    logger.setLevel(logging.DEBUG)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
    logger.addHandler(streamhandler)
    alive = threading.Event()
    alive.set()
    fipmeta = FIPMetadata(alive)
    fipmeta.start()
    time.sleep(3)
    while fipmeta.remains > 0:
        sys.stdout.write(f"\rWaiting {fipmeta.remains:.0f}s for cache to fill...")
        sys.stdout.flush()
        time.sleep(1)
    try:
        while True:
            time.sleep(5)
            print(f'{fipmeta.slug}: {fipmeta.remains:.0f} / {fipmeta.duration:.0f}')
    except KeyboardInterrupt:
        alive.clear()
        fipmeta.join()
