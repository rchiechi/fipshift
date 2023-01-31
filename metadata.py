import threading
import time
import requests
import logging
from urllib3.exceptions import ReadTimeoutError

METAURL = 'https://www.radiofrance.fr/api/v2.1/stations/fip/live'

JSON_TEMPLATE = {
                "delayToRefresh": 71000,
                "now": {
                  "firstLine": {
                    "id": None,
                    "title": "Le song",
                    "path": None
                  },
                  "secondLine": {
                    "id": None,
                    "title": "Le artist",
                    "path": None
                  },
                  "startTime": 1674841371,
                  "visuals": {
                    "card": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/250x250_rf_omm_0000232973_dnc.0057839972.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/250x250_rf_omm_0000232973_dnc.0057839972.webp",
                      "legend": None,
                      "width": 250,
                      "height": 250,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAgMEBQAB/8QAJhAAAQMDAwQCAwAAAAAAAAAAAQACAwQREiExQRMUQlEFIlJhgf/EABYBAQEBAAAAAAAAAAAAAAAAAAIAAf/EABYRAQEBAAAAAAAAAAAAAAAAAAABEf/aAAwDAQACEQMRAD8AbI/oR5OJ/qlknjey2bib7Kv5VhMAI2BWXA0iQEjRE1GVPvdwKtpakSDBhyIQlkT4rWbdL+NDI5pCXD0FNq3J/wCK77+k668v+lDpdXGJIS3k7KWpjZjGxxDdNVe4AiyxawvE9pRY8FVUVRwx62dwlQsaJDjxqUDWgR+WRTInBlO5oH2J1WE0ojlE0n0iQxOa6NuJuLIkgDkQdUFVTtqYS3y4KcAu8wsTGo2SOqOjISA3cJnQPcFhdjf3ytEtHcg2F7IZwOq02F1YWhhg7dlg4lNyHtMOyCw9LWP/2Q=="
                    },
                    "player": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/200x200_rf_omm_0000232973_dnc.0057839972.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/200x200_rf_omm_0000232973_dnc.0057839972.webp",
                      "legend": None,
                      "width": 200,
                      "height": 200,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAgMEBQAB/8QAJhAAAQMDAwQCAwAAAAAAAAAAAQACAwQREiExQRMUQlEFIlJhgf/EABYBAQEBAAAAAAAAAAAAAAAAAAIAAf/EABYRAQEBAAAAAAAAAAAAAAAAAAABEf/aAAwDAQACEQMRAD8AbI/oR5OJ/qlknjey2bib7Kv5VhMAI2BWXA0iQEjRE1GVPvdwKtpakSDBhyIQlkT4rWbdL+NDI5pCXD0FNq3J/wCK77+k668v+lDpdXGJIS3k7KWpjZjGxxDdNVe4AiyxawvE9pRY8FVUVRwx62dwlQsaJDjxqUDWgR+WRTInBlO5oH2J1WE0ojlE0n0iQxOa6NuJuLIkgDkQdUFVTtqYS3y4KcAu8wsTGo2SOqOjISA3cJnQPcFhdjf3ytEtHcg2F7IZwOq02F1YWhhg7dlg4lNyHtMOyCw9LWP/2Q=="
                    }
                  },
                  "producer": "",
                  "song": {
                    "id": "11cd7a76-06f5-4b5f-965d-2335a2d2930b",
                    "year": 1966,
                    "release": {
                      "label": "ATLANTIC",
                      "title": "Le album",
                      "reference": None
                    }
                  },
                  "stationName": "fip",
                  "endTime": 1674841528,
                  "media": {
                    "sources": [
                      {
                        "url": "https://stream.radiofrance.fr/fip/fip.m3u8?id=radiofrance",
                        "broadcastType": "live",
                        "format": "hls",
                        "bitrate": 0
                      },
                      {
                        "url": "https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance",
                        "broadcastType": "live",
                        "format": "aac",
                        "bitrate": 192
                      },
                      {
                        "url": "https://icecast.radiofrance.fr/fip-midfi.aac?id=radiofrance",
                        "broadcastType": "live",
                        "format": "aac",
                        "bitrate": 128
                      },
                      {
                        "url": "https://icecast.radiofrance.fr/fip-midfi.mp3?id=radiofrance",
                        "broadcastType": "live",
                        "format": "mp3",
                        "bitrate": 128
                      },
                      {
                        "url": "https://icecast.radiofrance.fr/fip-lofi.aac?id=radiofrance",
                        "broadcastType": "live",
                        "format": "aac",
                        "bitrate": 32
                      },
                      {
                        "url": "https://icecast.radiofrance.fr/fip-lofi.mp3?id=radiofrance",
                        "broadcastType": "live",
                        "format": "mp3",
                        "bitrate": 32
                      }
                    ],
                    "startTime": 1674841371,
                    "endTime": 1674841528
                  },
                  "localRadios": [],
                  "remoteDTR": 71000,
                  "nowTime": 1674841458,
                  "nowPercent": 55.4140127388535
                },
                "migrated": True,
                "next": {
                  "firstLine": {
                    "id": None,
                    "title": "Fish fare",
                    "path": None
                  },
                  "secondLine": {
                    "id": None,
                    "title": "Freddie King",
                    "path": None
                  },
                  "startTime": 1674841528,
                  "visuals": {
                    "card": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/2edfbbb5-2940-4f40-b0fa-0ddf188a4f92/400x400_rf_omm_0000513506_dnc.0053002059.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/2edfbbb5-2940-4f40-b0fa-0ddf188a4f92/400x400_rf_omm_0000513506_dnc.0053002059.webp",
                      "legend": None,
                      "width": 400,
                      "height": 400,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQABAAMBAQAAAAAAAAAAAAAABAIDBQEA/8QAKRAAAgIBAwMDAwUAAAAAAAAAAQIAAxEEEiETIjEFQVEUI3EzNGFygf/EABgBAAMBAQAAAAAAAAAAAAAAAAECBAMA/8QAHREAAgMAAgMAAAAAAAAAAAAAAAECERIDIjEyYf/aAAwDAQACEQMRAD8AlZpXrQM1uPzOV0WuMrYD/IMs9QXr7MHtHmWaGtKiyqCM88zLI+iCae5SCznHuJw1aghsP75z8R1jhEZj7CGp6l6FrO3PjEWUUlZ1lNXWFi5szzNGDCDq7Axz84iwvHkzKfwF2ZCanrs1fgkdsvqv+ms23qVZhwYBdNdt6gWaN+na/TVFz3L5MqtMB5TvuCOc7jkxzADAHxM3RWLbrSMZCjiaVkz5F1ORWpBfxzLYWv8AUEVJ5xywp2Zaa5BWAVO4cRFeoW0bXGOIRwOeJHR87/6mWYUfALsdodPQmbaSTu45inhfS/2g/JiW8/5E5PVhQWlbTeWd1C+wEZDVj7sTJpO2E//Z"
                    },
                    "player": None
                  },
                  "producer": "",
                  "song": {
                    "id": "9bfb38ac-47e7-4ba7-a314-94d76d18166f",
                    "year": 1961,
                    "release": {
                      "label": "MODERN BLUES",
                      "title": "Just pickin'",
                      "reference": None
                    }
                  },
                  "endTime": 1674841671
                }
              }

logger = logging.getLogger(__package__)


class FIPMetadata(threading.Thread):

    _newtrack = False
    metadata = JSON_TEMPLATE
    metaurl = METAURL

    def __init__(self, _alive):
        threading.Thread.__init__(self)
        self.name = 'Metadata Thread'
        self.alive = _alive
        self.last_update = time.time()

    def run(self):
        logger.info(f"Starting {self.name}")
        self.endtime = time.time() + 30
        session = requests.Session()
        while self.alive.is_set():
            if time.time() - self.last_update > 300:
                self.endtime = time.time()
                logger.warn('Metadata: Forcing update.')
            time.sleep(1)
            self.__updatemetadata(session)

        logger.info(f"{self.name} dying")

    def __updatemetadata(self, session):
        self.last_update = time.time()
        if self.remains > 0:
            return
        self._newtrack = True
        try:
            r = session.get(self.metaurl, timeout=5)
            self.metadata = r.json()
        except requests.exceptions.JSONDecodeError:
            logger.error("JSON error fetching metadata from Fip.")
            self.endtime = time.time() + 10
            pass
        except ReadTimeoutError:
            pass
        if self.metadata is None:
            self.metadata = JSON_TEMPLATE
            self.endtime = time.time() + 10
            logger.error("Error fetching metadata from Fip.")
        for _k in JSON_TEMPLATE['now']:
            if _k not in self.metadata['now']:
                self.metadata['now'][_k] = JSON_TEMPLATE['now'][_k]
                logger.debug('%s key mangled in update', _k)

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
        return {
            'track': track,
            'artist': artist,
            'album': album,
            'year': year,
            'coverart': coverart,
            'endTime': endtime
        }

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
        return self.endtime - time.time()

    @property
    def endtime(self):
        return self.getcurrent()['endTime']

    @endtime.setter
    def endtime(self, _time):
        self.metadata['now']['endTime'] = _time

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
            print(f'{fipmeta.slug}: {fipmeta.remains}')
    except KeyboardInterrupt:
        alive.clear()
        fipmeta.join()
