import os
import threading
import time
import json
import logging
import requests  # type: ignore
from fiphifi.constants import METAURL, METATEMPLATE  # type: ignore

logger = logging.getLogger(__package__)


class FIPMetadata(threading.Thread):

    metadata = METATEMPLATE
    metaurl = METAURL

    def __init__(self, _alive, tmpdir):
        threading.Thread.__init__(self)
        self.name = 'Metadata Thread'
        self._alive = _alive
        self._lock = threading.Lock()
        self._cache = os.path.join(tmpdir, 'metadata.json')
        with open(self.cache, 'wt') as fh:
            json.dump({}, fh)
        self.last_update = time.time()

    def run(self):
        logger.info(f"Starting {self.name}")
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        self.endtime = time.time() + 10
        while self.alive:
            if time.time() - self.last_update > 300:
                logger.debug('%s: Forcing update.', self.name)
            elif self.remains > 0:
                continue
            _delay = self._updatemetadata(requests.Session())
            self._writetodisk()
            for _ in range(_delay):
                if self.alive:
                    time.sleep(1)
        logger.info('%s dying (alive: %s)', self.name, self.alive)

    def _updatemetadata(self, session):
        if not self.alive:
            return 300000
        logger.info("%s fetching metadata from Fip", self.name)
        self.last_update = time.time()
        try:
            _json = {}
            _r = session.get(self.metaurl, timeout=5)
            if _r.status_code != 200:
                logger.warning('%s error fetching metadata: %s', self.name, _r.status_code)
                return 5
            else:
                _json = _r.json()
            if _json.get('now', {'endTime': None})['endTime'] is None:
                logger.debug('%s le nonsense endTime.', self.name)
                # return int(_json.get('delayToRefresh', 10000,) / 1000)
        except requests.exceptions.JSONDecodeError:
            logger.error("%s JSON error fetching metadata from Fip.", self.name)
            return 5
        except requests.ReadTimeout:
            logger.error("%s: GET request timed out.", self.name)
            return 5
        # for _k in METATEMPLATE['now']:
        #     if _k not in self.metadata['now']:
        #         self.metadata['now'][_k] = METATEMPLATE['now'][_k]
        #         logger.debug('%s %s key mangled in update', self.name, _k)
        self.metadata = _json
        return int(_json.get('delayToRefresh', 300000) / 1000)

    def _writetodisk(self):
        _json = self._readfromdisk()
        with self.lock:
            _metadata = self.current
            _json[int(_metadata['startTime'])] = _metadata
            _metadata = self.next
            _json[int(_metadata['startTime'])] = _metadata
            with open(self.cache, 'wt') as fh:
                logger.debug("%s writing json to %s", self.name, self.cache)
                json.dump(_json, fh)

    def _readfromdisk(self):
        with self.lock:
            with open(self.cache, 'rt') as fh:
                return json.load(fh)

    def _getmeta(self, when):
        _metadata = self.metadata.get(when, METATEMPLATE[when])
        if _metadata['song'] is None:
            _metadata['song'] = {'release': {'title': 'Le Album'}, 'year': 1977}
        delayToRefresh = float(self.metadata.get('delayToRefresh', 10000)) / 1000
        startTime = float(_metadata['startTime'] or time.time())
        endTime = float(_metadata['endTime'] or time.time() + 10)
        return {
            'track': _metadata['firstLine']['title'],
            'artist': _metadata['secondLine']['title'],
            'album': _metadata['song']['release']['title'],
            'year': _metadata['song']['year'],
            'coverart': _metadata['visuals']['card']['src'],
            'endTime': endTime,
            'startTime': startTime,
            'delayToRefresh': delayToRefresh
        }
        # try:
        #     track = self.metadata[when]['firstLine']['title']
        # except (KeyError, TypeError):
        #     track = 'Le track'
        # try:
        #     artist = self.metadata[when]['secondLine']['title']
        # except (KeyError, TypeError):
        #     artist = 'Le artist'
        # try:
        #     album = self.metadata[when]['song']['release']['title']
        # except (KeyError, TypeError):
        #     album = 'Le album'
        # try:
        #     year = self.metadata[when]['song']['year']
        # except (KeyError, TypeError):
        #     year = '1789'
        # try:
        #     coverart = self.metadata[when]['visuals']['card']['src']
        # except (KeyError, TypeError):
        #     coverart = 'https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/250x250_visual-fip.jpg'
        # try:
        #     endtime = float(self.metadata[when]['endTime'])
        # except (KeyError, TypeError):
        #     endtime = time.time() + 10
        # try:
        #     starttime = float(self.metadata[when]['startTime'])
        # except (KeyError, TypeError):
        #     starttime = time.time()
        # try:
        #     refresh = float(self.metadata['delayToRefresh']) / 1000
        # except (KeyError, TypeError):
        #     refresh = 0


    @property
    def current(self):
        return self._getmeta('now')

    @property
    def next(self):
        return self._getmeta('next')

    @property
    def cache(self):
        return self._cache

    @property
    def lock(self):
        return self._lock

    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def jsoncache(self):
        return self._readfromdisk()

    @property
    def remains(self):
        _remains = self.current['endTime'] - time.time()
        if _remains < 0:
            _remains = 0
        return _remains

    # @property
    # def track(self):
    #     return self.current['track']

    # @property
    # def artist(self):
    #     return self.current['artist']

    # @property
    # def album(self):
    #     return self.current['album']

    # @property
    # def year(self):
    #     return self.current['year']

    # @property
    # def coverart(self):
    #     return self.current['coverart']

    # @property
    # def slug(self):
    #     if self.album == 'Le album':
    #         return f'{self.track} - {self.artist}'
    #     return f'{self.track} - {self.artist} - {self.album}'

    # @property
    # def duration(self):
    #     _duration = self.endtime - self.starttime
    #     if _duration < 0:
    #         _duration = 0
    #     return _duration

    # @property
    # def starttime(self):
    #     return self.current['startTime']

    # @property
    # def endtime(self):
    #     return self.current['endTime']

    # @endtime.setter
    # def endtime(self, _time):
    #     self.metadata['now']['endTime'] = _time

    # @property
    # def lastupdate(self):
    #     return time.time() - self.last_update

    # @property
    # def refresh(self):
    #     _refresh = self.current['delayToRefresh'] - self.lastupdate
    #     if _refresh < 0:
    #         _refresh = 0
    #     return _refresh

# Metadata channel

# GET /admin/metadata?pass=hackme&mode=updinfo&mount=/mp3test&song=Even%20more%20meta%21%21 HTTP/1.0
# Authorization: Basic c291cmNlOmhhY2ttZQ==
# User-Agent: (Mozilla Compatible)


# if __name__ == '__main__':
#     import sys
#     logger.setLevel(logging.DEBUG)
#     streamhandler = logging.StreamHandler()
#     streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
#     logger.addHandler(streamhandler)
#     alive = threading.Event()
#     alive.set()
#     fipmeta = FIPMetadata(alive)
#     fipmeta.start()
#     time.sleep(3)
#     while fipmeta.remains > 0:
#         sys.stdout.write(f"\rWaiting {fipmeta.remains:.0f}s for cache to fill...")
#         sys.stdout.flush()
#         time.sleep(1)
#     try:
#         while True:
#             time.sleep(5)
#             print(f'{fipmeta.slug}: {fipmeta.remains:.0f} / {fipmeta.duration:.0f}')
#     except KeyboardInterrupt:
#         alive.clear()
#         fipmeta.join()
