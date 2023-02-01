import os
import sys
import time
import logging
import threading
import queue
import subprocess
from tempfile import TemporaryDirectory
import re
from metadata import FIPMetadata
import requests
from mutagen.mp3 import EasyMP3 as MP3

FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
FIPBASEURL = 'https://stream.radiofrance.fr'
AACRE = re.compile(f'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
TSRE= re.compile('(.*/fip_aac_hifi_\d_)(\d+)_(\d+)')
# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class FipPlaylist(threading.Thread):

    def __init__(self, alive, _queue):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self.alive = alive
        self.buff = _queue
        self.history = []

    def run(self):
        logger.info('Starting %s', self.name)
        fip_error = False
        session = requests.Session()
        while self.alive.is_set():
            req = session.get(FIPLIST, timeout=2)
            time.sleep(1)
            try:
                self.parselist(req.text)
                retries = 0
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("A ConnectionError has occured: %s", error)
            except requests.exceptions.Timeout:
                self.__guess()
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
            if len(self.history) > 1024:
                self.history = self.history[1024:]

        logger.info('%s dying', self.name)

    def __guess(self):
        logger.warn("Guessing at next TS file")
        _last = self.history[-1]
        m = re.search(TSRE, _last)
        if m is None:
            logger.error("Error guessing : (")
            return
        if len(m.groups()) < 3:
            logger.error("Error parsing ts file")
            return
        _url, _first, _second = m.groups()[0:3]
        _i = int(_second)
        for _ in range(5):
            _i += 1
            self.buff.put(f'{FIPBASEURL}{_url}{_first}{_i}')

    def parselist(self, _m3u):
        if not _m3u:
            return
        _urlz = []
        for _l in _m3u.split('\n'):
            if not _l:
                continue
            if _l[0] == '#':
                continue
            if _l not in self.history:
                _urlz.append(_l)
                self.history.append(_l)
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
        self.spool = os.path.join(self.tmpdir, 'spool.bin')
        self.cue = os.path.join(self.tmpdir, 'metdata.txt')
        self.ffmpeg = kwargs.get('ffmpeg', '/usr/bin/ffmpeg')
        self.fipmeta = FIPMetadata(self.alive)
        logging.getLogger("urllib3").setLevel(logging.WARN)

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
        if not self.fipmeta.is_alive():
            logger.warn("%s: Metadata thread died, restarting", self.name)
            self.fipmeta = FIPMetadata(self.alive)
        if not _chunk:
            logger.warn("%s empty chunk", self.name)
            return
        with open(self.spool, 'ab') as fh:
            fh.write(_chunk)
        _chunk_kb = os.stat(self.spool).st_size/1024
        if not self.fipmeta.newtrack:
            if _chunk_kb/1024 > 5:
                logger.debug('Spool exceeds 5 MB, processing.')
            else:
                return
        elif _chunk_kb < 1024:
            logger.debug('Not processing spool < 1MB')
            return
        fn = os.path.join(self.tmpdir, f'{_fn}.mp3')
        self.__ffmpeg(fn)
        _meta = self.fipmeta.slug
        if os.path.exists(fn):
            self.filequeue.put((fn, _meta))
        else:
            logger.error("Failed to create %s", fn)
        with self.lock:
            with open(self.cue, 'at') as fh:
                fh.write(f'{fn}%{_meta}\n')
            self.metamap[fn] = _meta
        self._empty = False

    def __ffmpeg(self, _out):
        subprocess.run([self.ffmpeg,
                        '-i', self.spool,
                        '-acodec', 'libmp3lame',
                        '-b:a', '192k',
                        '-f', 'mp3',
                        '-y',
                        _out],
                       cwd=self.tmpdir,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        os.unlink(self.spool)
        _mp3 = MP3(_out)
        _mp3['title'] = self.fipmeta.track
        _mp3['artist'] = self.fipmeta.artist
        _mp3['album'] = self.fipmeta.album
        _mp3.save()
        self._empty = True

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

    playing = False

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
        self.ezstream = kwargs.get('ezstream', '/usr/local/bin/ezstream')
        _tmpdir = kwargs.get('tmpdir', '/tmp/fipshift/ezstream')
        self.ezstreamxml = os.path.join(_tmpdir, 'ezstream.xml')

    def run(self):
        logger.info('Starting %s', self.name)
        while self.filequeue.empty():
            logger.info('%s waiting for queue to fill.', self.name)
            time.sleep(10)
        lastmeta = ''
        restart = True
        _ezcmd = [self.ezstream, '-c', self.ezstreamxml]
        while self.alive.is_set():
            if restart:
                restart = False
                self.playing = False
                logger.warn("Restarting ezstream")
                ezstream = subprocess.Popen(_ezcmd, stdin=subprocess.PIPE)
            if self.filequeue.empty():
                self.playing = False
                restart = True
                logger.warn('%s: empty queue, pausing for 60s.', self.name)
                time.sleep(60)
                continue
            _fn, _meta = self.filequeue.get()
            if _meta != lastmeta:
                lastmeta = _meta
                try:
                    self.__updatemetadata(_meta)
                except requests.exceptions.ConnectionError as msg:
                    logger.warning('Metadata: %s: %s', self.name, msg)
            else:
                logger.debug('%s: Metadata unchanged', self.name)
            if ezstream.poll() is not None:
                logger.warning("Ezstream died.")
                restart = True
                continue
            self.playing = True
            with open(_fn, 'rb') as fh:
                logger.debug('%s sending %s', self.name, _fn)
                ezstream.stdin.write(fh.read())

            os.unlink(_fn)
            logger.debug("Cleaned up %s", _fn)
        ezstream.kill()
        logger.info('%s dying', self.name)

    def __updatemetadata(self, _meta):
        _params = {
            'mode': 'updinfo',
            'mount': f'/{self.mount}',
            'song': _meta
        }
        _url = f'{self.iceserver}/admin/metadata?{_params}'
        req = requests.get(_url, params=_params, auth=self.auth)
        if 'Metadata update successful' in req.text:
            logger.debug('Metadata updated successfully')
        else:
            logger.debug('Error updated metadata: %s', req.text.strip())

    @property
    def streaming(self):
        return self.playing

if __name__ == '__main__':
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
    dl = FipChunks(alive, lock, _queue, ffmpeg='/home/rchiechi/bin/ffmpeg')
    EZSTREAMCONFIG = os.path.join(dl.tmpdir, 'ezstream.xml')
    with open(os.path.join(os.path.dirname(
        os.path.realpath(__file__)), 'ezstream.xml'), 'rt') as fr:
        rep = {'%PLAYLIST%': os.path.join(dl.tmpdir, 'fifo.mp3'),
            '%HOST%': '127.0.0.1',
            '%PORT%': '8000',
            '%PASSWORD%': 'im08en',
            '%MOUNT%':'fipshift'}
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
    with open(EZSTREAMCONFIG, 'wt') as fw:
        fw.write(xml)
    ezstreamcast = Ezstream(alive, lock, dl.filequeue,
                            tmpdir=dl.tmpdir,
                            auth=('source', 'hackme')
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
