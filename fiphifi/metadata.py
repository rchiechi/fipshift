import os
import threading
import time
import json
import logging
import requests  # type: ignore
from fiphifi.constants import METAURL, METATEMPLATE  # type: ignore

logger = logging.getLogger(__package__+'.metadata')


def send_metadata(url, mount, slug, auth):
    _params = {'mode': 'updinfo',
               'mount': f"/{mount}",
               'song': slug}
    try:
        req = requests.get(f'http://{url}/admin/metadata', params=_params,
                           auth=requests.auth.HTTPBasicAuth(*auth))
        if 'Metadata update successful' in req.text:
            logger.info('Metadata udpate: %s', slug)
            return True
        else:
            logger.warning('Error updating metdata (%s): %s', url, req.text)
            return False
    except (requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError):
        logger.warning('Metadata update failed to communicate with icecast.')


class FIPMetadata(threading.Thread):

    metadata = METATEMPLATE
    metaurl = METAURL

    def __init__(self, _alive, tmpdir):
        threading.Thread.__init__(self)
        self.name = 'Metadata Thread'
        self._alive = _alive
        self._lock = threading.Lock()
        self._cache = os.path.join(tmpdir, 'metadata.json')
        self.last_update = time.time()

    def run(self):
        logger.info(f"Starting {self.name}")
        if not os.path.exists(self.cache):
            with open(self.cache, 'wt') as fh:
                json.dump({}, fh)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
        self._updatemetadata()
        self._writetodisk()
        while self.alive:
            if time.time() - self.last_update > 300:
                logger.debug('%s: Forcing update.', self.name)
            elif self.remains > 0:
                time.sleep(1)
                continue
            _delay = self._updatemetadata()
            self._writetodisk()
            logger.debug("%s wrote %s", self.name, self.current)
            for _ in range(_delay):
                if self.alive:
                    time.sleep(1)
        logger.warning('%s ended (alive: %s)', self.name, self.alive)

    def _updatemetadata(self):
        if not self.alive:
            return 300000
        logger.info("%s fetching metadata from Fip", self.name)
        self.last_update = time.time()
        try:
            _json = {}
            _r = requests.get(self.metaurl, timeout=5)
            if _r.status_code != 200:
                logger.warning('%s error fetching metadata: %s', self.name, _r.status_code)
                return 5
            else:
                _json = _r.json()
            if _json.get('now', {'endTime': None})['endTime'] is None:
                logger.debug('%s le nonsense endTime.', self.name)
                return 5
        except json.JSONDecodeError:
            logger.error("%s JSON error fetching metadata from Fip.", self.name)
            return 5
        except requests.exceptions.ReadTimeout:
            logger.error("%s: GET request timed out.", self.name)
            return 5
        except requests.exceptions.ConnectionError:
            logger.error("%s: ConnectionError.", self.name)
            return 5
        self.metadata = _json
        return int(_json.get('delayToRefresh', 300000) / 1000)

    def _writetodisk(self, _json=None):
        if _json is None:
            _json = self._readfromdisk()
        with self.lock:
            _metadata = self.current
            _now = int(_metadata['startTime'])
            _json[_now] = _metadata
            _metadata = self.next
            _next = int(_metadata['startTime'])
            if _next not in _json:
                _json[_next] = _metadata
            with open(self.cache, 'wt') as fh:
                json.dump(_json, fh)

    def _readfromdisk(self):
        _metadata = {}
        with self.lock:
            with open(self.cache, 'rt') as fh:
                try:
                    _metadata = json.load(fh)
                except json.JSONDecodeError:
                    pass
        return _metadata

    def _getmeta(self, when):
        if when not in self.metadata:
            logger.warning("%s key %s not found, returning template.", self.name, when)
        _metadata = self.metadata.get(when, METATEMPLATE[when])
        if isinstance(_metadata, list):
            _metadata = _metadata[0]
        if not isinstance(_metadata, dict):
            logger.warn("%s metadata is: %s", self.name, _metadata)
            _metadata = {}
        if _metadata.get('song', None) is None:
            _metadata['song'] = METATEMPLATE['now']['song']
        try:
            _metadata.get('song', {}).get('release', {}).get('title', 'Le Album')
        except AttributeError:
            logger.warn("%s error parsing song: %s", self.name, _metadata)
            _metadata['song'] = METATEMPLATE['now']['song']

        metadata = {'delayToRefresh': float(self.metadata.get('delayToRefresh', 10000)) / 1000,
                    'track': _metadata.get('firstLine', {'tile':'Le Title'})['title'],
                    'artist': _metadata.get('secondLine', {'title':'Le Artist'})['title'],
                    'album': _metadata.get('song', {}).get('release', {}).get('title', 'Le Album'),
                    'year': _metadata.get('song', {}).get('year', 1977),
                    'coverart': _metadata.get('visuals', {}).get('card', {}).get('src'),
                    'startTime': float(_metadata.get('startTime', 0) or time.time()),
                    'endTime': float(_metadata.get('endTime', 0) or time.time() + 10)}
        return metadata

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

    @jsoncache.setter
    def jsoncache(self, _json):
        self._writetodisk(_json)

    @property
    def remains(self):
        _remains = self.current['endTime'] - time.time()
        if _remains < 0:
            _remains = 0
        return _remains
