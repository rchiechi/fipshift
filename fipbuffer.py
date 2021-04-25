'''Open FIP MP3 url and buffer it to disk for time-shifted re-streaming.'''

import os
import sys
import urllib.request
import json
import threading
import queue
import time


FIPURL='http://icecast.radiofrance.fr/fip-midfi.mp3'
#FIPURL='https://icecast.radiofrance.fr/fip-hifi.aac'
BLOCKSIZE=1024*128
# pylint: disable=missing-class-docstring, missing-function-docstring

class FIPBuffer(threading.Thread):

    def __init__(self, _alive, _fqueue, _tmpdir):
        threading.Thread.__init__(self)
        self.setName('File Buffer Thread')
        self.fipmetadata = FIPMetadata()
        self.alive = _alive
        self.fqueue = _fqueue
        self.tmpdir = _tmpdir
        self.f_counter=0
        self.t_start = time.time()

    def run(self):
        print("Starting %s" % self.getName())
        req = urllib.request.urlopen(FIPURL, timeout=10)
        while True:
            buff = req.read(BLOCKSIZE)
            if not buff:
                print("%s: emtpy block, dying." % self.getName())
                self.alive.clear()
                break
            #print("%s: fetching block" % self.getName())
            fn = os.path.join(self.tmpdir, self.getfn())
            with open(fn, 'wb') as fh:
                fh.write(buff)
                self.fqueue.put( 
                    (time.time(), fn, self.fipmetadata.getcurrent()) 
                    )
                #print("\r%s: wrote %s" % (self.getName(), fn))
            self.f_counter += 1
            if not self.alive.is_set():
                print("%s: dying." % self.getName())
                break

    def getfn(self):
        return str(self.f_counter).zfill(16)
    def getruntime(self):
        return time.time() - self.t_start


class FIPMetadata():

    metadata={"prev":
        [{"firstLine":"FIP",
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
           "now":{
               "firstLine":"FIP",
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

    def __init__(self):
        self.metaurl = 'https://api.radiofrance.fr/livemeta/live/7/fip_player'
        self.metadata = {}
        self.__updatemetadata()

    def getcurrent(self):
        if time.time() > self.metadata['now']['endTime']:
            self.__updatemetadata()
        return {
            'track': self.metadata['now']['secondLine'],
            'artist': self.metadata['now']['thirdLine']
        }

    def getcurrenttrack(self):
        return self.getcurrent()['track']
    def getcurrentartist(self):
        return self.getcurrent()['artist']

    def __updatemetadata(self):
        r = urllib.request.urlopen(self.metaurl, timeout=5)
        try:
            self.metadata = json.loads(r.read())
        except json.decoder.JSONDecodeError:
            self.metadata = {}
        if 'now' not in self.metadata:
            self.metadata = FIPMetadata.metadata


if __name__ == "__main__":

    fipmeta = FIPMetadata()
    print(fipmeta.getcurrent())
    sys.exit()

    TMPDIR='/tmp/fipshift'
    buffertime = 60
    if not os.path.exists(TMPDIR):
        os.mkdir(TMPDIR)
    for tmpfn in os.listdir(TMPDIR):
        print(os.path.join(TMPDIR,tmpfn))
        os.remove(os.path.join(TMPDIR,tmpfn))
    alive = threading.Event()
    fqueue = queue.Queue()
    alive.set()
    fipbuffer = FIPBuffer(alive, fqueue, TMPDIR)
    fipbuffer.start()
    time.sleep(1)
    while True:
        try:
            print("Thread running for %0.1f seconds" % fipbuffer.getruntime())
            print("Wrote %s files (%s kb)" % (
                int(fipbuffer.getfn()), int(fipbuffer.getfn())*BLOCKSIZE) )
            if time.time() - fipbuffer.getruntime() > buffertime:
                _f = fqueue.get()
                while time.time() - _f[0] < buffertime:
                    time.sleep(0.1)
                print("Deleting %s" % _f[1])
                os.remove(os.path.join(TMPDIR, _f[1]))
            time.sleep(3)
        except KeyboardInterrupt:
            print("Killing %s" % fipbuffer.getName())
            alive.clear()
            fipbuffer.join()
            break
