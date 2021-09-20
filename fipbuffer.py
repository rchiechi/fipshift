'''Open FIP MP3 url and buffer it to disk for time-shifted re-streaming.'''

import os
import urllib.request
import json
import threading
import time
from socket import timeout as socket_timeout

# pylint: disable=missing-class-docstring, missing-function-docstring

FIPURL = 'http://icecast.radiofrance.fr/fip-midfi.mp3'
BLOCKSIZE = 1024*128

class FIPBuffer(threading.Thread):

    def __init__(self, _alive, _fqueue, _tmpdir):
        threading.Thread.__init__(self)
        self.setName('File Buffer Thread')
        self.alive = _alive
        self.fqueue = _fqueue
        self.tmpdir = _tmpdir
        self.f_counter = 0
        self.t_start = time.time()
        self.fipmetadata = FIPMetadata(_alive)

    def run(self):
        print("Starting %s" % self.getName())
        self.fipmetadata.start()
        req = urllib.request.urlopen(FIPURL, timeout=10)
        retries = 0
        while self.alive.is_set():
            try:
                buff = req.read(BLOCKSIZE)
                retries = 0
            except socket_timeout:
                retries += 1
                if retries > 9:
                    buff = ''
                else:
                    req = urllib.request.urlopen(FIPURL, timeout=10)
                    continue
            if not buff:
                print("\n%s: emtpy block after %s retries, dying.\n" % retries, self.getName())
                self.alive.clear()
                break
            fn = os.path.join(self.tmpdir, self.getfn())
            with open(fn, 'wb') as fh:
                fh.write(buff)
                # Check here if file was created?
                self.fqueue.put(
                    (time.time(), fn, self.fipmetadata.getcurrent())
                )
            self.f_counter += 1
            # For whatever reason resetting the counter leads to filenotfound in main thread.
            # if self.getruntime() > 24*3600:
            #     self.f_counter = 0  # Reset file counter every 24 hours
        print("%s: dying." % self.getName())
        self.fipmetadata.join()

    def getfn(self):
        return str(self.f_counter).zfill(16)

    def getruntime(self):
        return time.time() - self.t_start

    def getstarttime(self):
        return self.t_start

    @classmethod
    def generateplaylist(self):
        _playlist = []
        for i in range(0,9999999999999999):
            _playlist.append(i.zfill(16))
        return _playlist


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
        print("Starting %s" % self.getName())
        while self.alive.is_set():
            self.__updatemetadata()
            time.sleep(3)
        print("%s: dying." % self.getName())

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

    def getcurrenttrack(self):
        return self.getcurrent()['track']

    def getcurrentartist(self):
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

# class IcesLogParser(threading.Thread):
# 
#     def __init__(self, _alive, _fqueue, _tmpdir):
#         threading.Thread.__init__(self)
#         self.setName('File Buffer Thread')
#         self.alive = _alive
#         self.fqueue = _fqueue
#         self.tmpdir = _tmpdir
#         self.f_counter = 0
#         self.t_start = time.time()
#         self.fipmetadata = FIPMetadata(_alive)

