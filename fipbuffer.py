'''Open FIP MP3 url and buffer it to disk for time-shifted re-streaming.'''

import os
import urllib.request
import json
import threading
import logging
import time
from urllib.error import HTTPError, URLError
from socket import timeout as socket_timeout
from mutagen.mp3 import EasyMP3 as MP3
from mutagen import MutagenError

# pylint: disable=missing-class-docstring, missing-function-docstring

FIPURL = 'http://icecast.radiofrance.fr/fip-midfi.mp3'
BLOCKSIZE = 1024*512

logger = logging.getLogger(__name__)

def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins

class FIPBuffer(threading.Thread):

    def __init__(self, _alive, _lock, _fqueue, _tmpdir, _playlist):
        threading.Thread.__init__(self)
        self.setName('File Buffer Thread')
        self.alive = _alive
        self.lock = _lock
        self.fqueue = _fqueue
        self.tmpdir = _tmpdir
        self.playlist = _playlist
        self.f_counter = 0
        self.t_start = time.time()
        self.fipmetadata = FIPMetadata(_alive)

    def run(self):
        print("Starting %s" % self.name)
        logger.info("%s: starting.", self.name)
        self.fipmetadata.start()
        req = urllib.request.urlopen(FIPURL, timeout=10)
        retries = 0
        fip_error = False
        while self.alive.is_set():
            try:
                buff = req.read(BLOCKSIZE)
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
                    buff = ''
                else:
                    logger.warning("Fip stream error, retrying (%s)", retries)
                    req = urllib.request.urlopen(FIPURL, timeout=10)
                    continue
            if not buff:
                print("\n%s: emtpy block after %s retries, dying.\n" % (retries, self.getName()))
                logger.error("%s: emtpy block after %s retries, dying.", retries, self.getName())
                self.alive.clear()
                break
            fn = os.path.join(self.tmpdir, self.getfn())
            with self.lock:
                with open(self.playlist, 'ab') as fh:
                    fh.write(bytes(fn, encoding='UTF-8')+b'\n')
            # with open(fn, 'wb') as fh:
            #     fh.write(buff)
            # try:
            #     _mp3 = MP3(fn)
            #     _mp3['artist'] = self.fipmetadata.currentartist
            #     _mp3['title'] = self.fipmetadata.currenttrack
            #     _mp3.save()
            # except MutagenError:
            #     logger.warn('Error writing metadata to %s', fn)

            self.f_counter += 1
        print("%s: dying." % self.name)
        logger.info("%s: dying.", self.name)
        self.fipmetadata.join()

    def getfn(self):
        return str(self.f_counter).zfill(16)

    def getruntime(self):
        return time.time() - self.t_start

    def getstarttime(self):
        return self.t_start

class FIPMetadata(threading.Thread):

    metadata = {"prev":[
               {"firstLine":"FIP",
                "secondLine":"Previous Track",
                "thirdLine":"Previous Artist",
                "cover":"Previous Cover",
                "startTime":0,"endTime":1},
               {"firstLine":"FIP",
                "secondLine":"Previous Track",
                "thirdLine":"Previous Artist",
                "cover":"Previous Cover",
                "startTime":2,
                "endTime":3},
               {"firstLine":"FIP",
                "secondLine":"Previous Track",
                "thirdLine":"Previous Artist",
                "cover":"Previous Cover",
                "startTime":4,
                "endTime":5}],
                "now":
                {"firstLine":"FIP",
                 "secondLine":"Current Track",
                 "thirdLine":"Current Artist",
                 "cover":"Current Cover",
                 "startTime":6,"endTime":7},
                "next":
                [{"firstLine":"FIP",
                  "secondLine":"Next Track",
                  "thirdLine":"Next Artist",
                  "cover":"Next Cover",
                  "startTime":8,
                  "endTime":9}],
                "delayToRefresh":220000}

    def __init__(self, _alive):
        threading.Thread.__init__(self)
        self.setName('Metadata Thread')
        self.alive = _alive
        self.metaurl = 'https://api.radiofrance.fr/livemeta/live/7/fip_player'

    def run(self):
        print("Starting %s" % self.name)
        logger.info("%s: starting.", self.name)
        while self.alive.is_set():
            self.__updatemetadata()
            time.sleep(3)
        print("%s: dying." % self.name)
        logger.info("%s: dying.", self.name)

    def getcurrent(self):
        track = self.metadata['now']['secondLine']
        artist = self.metadata['now']['thirdLine']
        if not isinstance(track, str):
            track = 'Error fetching track'
        if not isinstance(artist, str):
            artist = 'Error fetching artist'
        return {
            'track': track,
            'artist': artist
        }

    @property
    def currenttrack(self):
        return self.getcurrent()['track']

    @property
    def currentartist(self):
        return self.getcurrent()['artist']

    def __updatemetadata(self):
        endtime = self.metadata['now']['endTime'] or 0
        if time.time() < endtime:
            return
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
