import os
import sys
import time
import logging
import threading
import queue
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
import re
import io
from metadata import FIPMetadata
import requests


FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
FIPBASEURL = 'https://stream.radiofrance.fr'
AACRE = re.compile(f'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    def __init__(self, alive, _queue):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self.alive = alive
        self.buff = _queue

    def run(self):
        logger.info('Starting %s', self.name)
        fip_error = False
        session = requests.Session()
        while self.alive.is_set():
            req = session.get(FIPLIST)
            time.sleep(1)
            try:
                self.parselist(req.text)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("A ConnectionError has occured: %s", error)
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
                    logger.warning("Fip playlist stream error, retrying (%s)", retries)
                    continue
        logger.info('%s dying', self.name)

    def parselist(self, _m3u):
        if not _m3u:
            return
        _urlz = []
        for _l in _m3u.split('\n'):
            if not _l:
                continue
            if _l[0] == '#':
                continue
            _urlz.append(_l)
        for _url in _urlz:
            self.buff.put(f'{FIPBASEURL}{_url}')


class FipChunks(threading.Thread):

    metamap = {}
    _empty = True

    def __init__(self, alive, lock, urlqueue, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'FipChunk Thread'
        self.alive = alive
        self.lock = lock
        self.urlqueue = urlqueue
        self.filequeue = queue.Queue()
        self._tmpdir = kwargs.get('tmpdir', TemporaryDirectory())
        self._spool = os.path.join(self.tmpdir, 'spool.bin')
        self.cue = os.path.join(self.tmpdir, 'metdata.txt')
        self.fipmeta = FIPMetadata(self.alive)

    def run(self):
        logger.info('Starting %s', self.name)
        self.fipmeta.start()
        fip_error = False
        session = requests.Session()
        while self.alive.is_set():
            if self.urlqueue.empty():
                time.sleep(1)
                continue
            _url = self.urlqueue.get()
            _m = re.match(AACRE, _url)
            if _m is None:
                logger.warning("Empty URL?")
                continue
            fn = _m.groups()[0]
            req = session.get(_url)
            try:
                self.__handlechunk(fn, req.content)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("A ConnectionError has occured: %s", error)
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
                    logger.warning("Fip playlist stream error, retrying (%s)", retries)
                    continue
        logger.info('%s dying', self.name)

    def __handlechunk(self, _fn, _chunk):
        self.__writespool(_chunk)
        if not self.fipmeta.newtrack:
            return
        chunk = self.__readspool()
        fn = os.path.join(self.tmpdir, _fn)
        with open(fn, 'wb') as fh:
            fh.write(chunk)
        _meta = self.fipmeta.slug
        self.filequeue.put((fn, _meta))
        with self.lock:
            with open(self.cue, 'at') as fh:
                fh.write(f'{fn}%{_meta}\n')
            self.metamap[fn] = _meta
        self._empty = False

    def __writespool(self, _chunk):
        with open(self._spool, 'ab') as fh:
            fh.write(_chunk)

    def __readspool(self):
        with open(self._spool, 'rb') as fh:
            _chunk = fh.read()
        os.unlink(self._spool)
        return _chunk

    @property
    def getmetadata(self, fn):
        _metamap = {}
        with self.lock:
            for _fn in self.metamap:
                if os.path.exists(_fn):
                    _metamap[_fn] = self.metamap[_fn]
            self.metamap = _metamap
        return _metamap.get(fn, '')

    @property
    def tmpdir(self):
        try:
            _tmpdir = self._tmpdir.name
        except AttributeError:
            _tmpdir = self._tmpdir
        with self.lock:
            return _tmpdir

    @tmpdir.setter
    def tmpdir(self, _dir):
        if os.path.exists(_dir):
            with self.lock:
                self._tmpdir = _dir

    @property
    def empty(self):
        return self._empty

    @property
    def remains(self):
        return self.fipmeta.remains


class Ezstream(threading.Thread):

    def __init__(self, alive, lock, filequeue, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'Ezstream Thread'
        self.alive = alive
        self.lock = lock
        self.filequeue = filequeue
        _server = kwargs.get('server', 'localhost')
        _port = kwargs.get('port', '8000')
        self.iceserver = f'http://{_server}:{_port}'
        self.mount = kwargs.get('mount', 'fipshift')
        _auth = kwargs.get('auth', ['', ''])
        self.auth = requests.auth.HTTPBasicAuth(_auth[0], _auth[1])
        self.ffmpeg = kwargs.get('ffmpeg', '/usr/bin/ffmpeg')
        self.ezstream = kwargs.get('ezstream', '/usr/local/bin/ezstream')
        self.ezstreamxml = kwargs.get('ezstreamxml', '/tmp/fipshift/ezstream/ezstream.xml')

    def run(self):
        logger.info('Starting %s', self.name)
        lastmeta = ''
        ezstream = subprocess.Popen([self.ezstream, '-c', self.ezstreamxml, '-q'],
                                    stdin=subprocess.PIPE)
                                    # ,
                                    # stderr=subprocess.PIPE,
                                    # stdout=subprocess.PIPE)

        while self.alive.is_set():
            # logger.debug('Ezstream: %s', ezstream.stdout.read())
            # logger.warn('Ezstream: %s', ezstream.stderr.read())
            if self.filequeue.empty():
                time.sleep(0.1)
                continue
            _fn, _meta = self.filequeue.get()
            if _meta != lastmeta:
                lastmeta = _meta
                try:
                    self.__updatemetadata(_meta)
                except requests.exceptions.ConnectionError as msg:
                    logger.warn('Metadata: %s: %s', self.name, msg)
            with self.lock:
                _ffmpeg = subprocess.Popen([self.ffmpeg,
                                            '-i', _fn,
                                            '-acodec', 'libmp3lame',
                                            '-b:a', '192k',
                                            '-f', 'mp3',
                                            'pipe:1'],
                                           stdout=ezstream.stdin,
                                           stderr=subprocess.PIPE)
                print(_ffmpeg.stderr.read())
                os.unlink(_fn)

    def __updatemetadata(self, _meta):
        _params = {
            'mode': 'updinfo',
            'mount': f'/{self.mount}',
            'song': _meta
        }
        _url = f'{self.iceserver}/admin/metadata?{_params}'
        req = requests.get(_url, params=_params, auth=self.auth)
        logger.debug('Metadata: %s', req.text)


if __name__ == '__main__':

    logger = logging.getLogger(__package__)
    logger.setLevel(logging.DEBUG)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    logger.addHandler(streamhandler)
    logging.getLogger("urllib3").setLevel(logging.WARN)
    alive = threading.Event()
    lock = threading.Lock()
    _queue = queue.Queue()
    alive.set()
    pl = FipPlaylist(alive, _queue)
    dl = FipChunks(alive, lock, _queue)
    EZSTREAMCONFIG = os.path.join(dl.tmpdir, 'ezstream.xml')
    with open(os.path.join(os.path.dirname(
        os.path.realpath(__file__)), 'ezstream.xml'), 'rt') as fr:
        rep = {'%HOST%': '127.0.0.1',
            '%PORT%': '8000',
            '%PASSWORD%': 'im08en',
            '%MOUNT%':'fipshift'}
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
    with open(EZSTREAMCONFIG, 'wt') as fw:
        fw.write(xml)
    ezstreamcast = Ezstream(alive, lock, dl.filequeue,
                            ffmpeg='/home/rchiechi/bin/ffmpeg',
                            ezstreamxml=EZSTREAMCONFIG,
                            auth=('source', 'im08en')
                            )
    try:
        pl.start()
        dl.start()
        time.sleep(3)
        logger.debug('tmpdir is %s', dl.tmpdir)
        while dl.remains > 0:
            sys.stdout.write(f"\rWaiting {dl.remains:.0f}s for cache to fill...")
            sys.stdout.flush()
            time.sleep(1)
        print('\nStarting cast.')
        ezstreamcast.start()
    except KeyboardInterrupt:
        alive.clear()
        ezstreamcast.join()
