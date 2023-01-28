import threading
import time
import urllib.request
from socket import timeout as socket_timeout
import logging
import base64
import json
from urllib.error import HTTPError, URLError

METAURL = 'https://www.radiofrance.fr/api/v2.1/stations/fip/live'

JSON_TEMPLATE ={
  "delayToRefresh": 71000,
  "now": {
    "firstLine": {
      "id": None,
      "title": "Shake",
      "path": None
    },
    "secondLine": {
      "id": None,
      "title": "Otis Redding",
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
        "title": "The Otis Redding story",
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

    def run(self):
        print("Starting %s" % self.name)
        logger.info("%s: starting.", self.name)
        while self.alive.is_set():
            self.__updatemetadata()
            time.sleep(3)
        print("%s: dying." % self.name)
        logger.info("%s: dying.", self.name)

    def __updatemetadata(self):
        endtime = self.metadata['now']['endTime'] or 0
        if time.time() < endtime:
            return
        self._newtrack = True
        self.metadata = FIPMetadata.metadata
        try:
            r = urllib.request.urlopen(self.metaurl, timeout=5)
            self.metadata = json.loads(r.read())
        except json.decoder.JSONDecodeError:
            pass
        except urllib.error.URLError:
            pass
        except socket_timeout:
            pass
        if 'now' not in self.metadata:
            self.metadata = FIPMetadata.metadata

    def _getmeta(self, when):
        track = self.metadata[when]['firstLine']['title']
        artist = self.metadata[when]['secondLine']['title']
        album = self.metadata[when]['song']['release']['title']
        year = self.metadata[when]['song']['year']
        coverart = self.metadata[when]['visuals']['card']['src']
        if not isinstance(track, str):
            track = 'Le track'
        if not isinstance(artist, str):
            artist = 'Le artist'
        if not isinstance(album, str):
            album = 'Le album'
        if not isinstance(year, int):
            year = '1789'
        if not isinstance(coverart, str):
            coverart = 'https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/250x250_visual-fip.jpg'
        return {
            'track': track,
            'artist': artist,
            'album': album,
            'year': year,
            'coverart': coverart
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
        return f'{self.track} - {self.artist} - {self.album}'

    @property
    def newtrack(self):
        if self._newtrack:
            self._newtrack = False
            return True
        return False

# Metadata channel

# GET /admin/metadata?pass=hackme&mode=updinfo&mount=/mp3test&song=Even%20more%20meta%21%21 HTTP/1.0
# Authorization: Basic c291cmNlOmhhY2ttZQ==
# User-Agent: (Mozilla Compatible)

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
    logger.addHandler(streamhandler)
    alive = threading.Event()
    alive.set()
    fipmeta = FIPMetadata(alive)
    fipmeta.start()
    while True:
        time.sleep(5)
        print(fipmeta.album)
        print(fipmeta.artist)
        print(fipmeta.album)
        print(fipmeta.year)
        print(fipmeta.coverart)