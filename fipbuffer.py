'''Open FIP MP3 url and buffer it to disk for time-shifted re-streaming.'''

import os
import urllib.request
import json
import threading
import logging
import time
from io import BytesIO
from metadata import FIPMetadata
from urllib.error import HTTPError, URLError
from socket import timeout as socket_timeout
from mp3 import detectlastframe
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

    _metadata = False

    def __init__(self, _alive, _lock, _fqueue, _tmpdir, _playlist=''):
        threading.Thread.__init__(self)
        self.name = 'File Buffer Thread'
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
        buff = BytesIO()
        while self.alive.is_set():
            try:
                buff.write(req.read(BLOCKSIZE))
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
                    logger.warning("Fip stream error, retrying (%s)", retries)
                    req = urllib.request.urlopen(FIPURL, timeout=10)
                    continue
            if self.fipmetadata.newtrack:
                logger.debug("New track detected.")
                buff = self.writebuff(buff)

        print("%s: dying." % self.name)
        logger.info("%s: dying.", self.name)
        self.fipmetadata.join()

    def writebuff(self, buff):
        _lastframe = detectlastframe(buff)
        fn = os.path.join(self.tmpdir, self.getfn())
        with open(fn, 'wb') as fh:
            buff.seek(0)
            fh.write(buff.read(_lastframe))
        self.f_counter += 1

        if self.fqueue is not None:
            self.enqueue(fn)
        if self.playlist:
            self.writetoplaylsit(fn)
        return BytesIO(buff.read())

    def getfn(self):
        return str(self.f_counter).zfill(16)

    def getruntime(self):
        return time.time() - self.t_start

    def getstarttime(self):
        return self.t_start

    def writetoplaylsit(self, _fn):
        fn = _fn
        if self.metadata:
            self.writetags(fn)
        with self.lock:
            with open(self.playlist, 'ab') as fh:
                fh.write(bytes(fn, encoding='UTF-8')+b'\n')

    def enqueue(self, fn):
        self.fqueue.put(
            (time.time(), fn, self.fipmetadata.getcurrent())
        )

    def writetags(self, fn):
        try:
            _mp3 = MP3(fn)
            _mp3['artist'] = self.fipmetadata.artist
            _mp3['title'] = self.fipmetadata.track
            _mp3['album'] = self.fipmetadata.album
            # _mp3['year'] = self.fipmetadata.year
            _mp3.save()
        except MutagenError as msg:
            logger.warn('Error writing metadata to %s:', fn, msg)

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, _bool):
        if _bool:
            self._metadata = True
        else:
            self._metadata = False
