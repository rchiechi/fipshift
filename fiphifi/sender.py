import os
import sys
import time
import logging
import threading
import queue
import subprocess
import re
from signal import SIGHUP
import requests  # type: ignore


# 'https://stream.radiofrance.fr/msl4/fip/prod1transcoder1/fip_aac_hifi_4_1673363954_368624.ts?id=radiofrance'

logger = logging.getLogger(__package__)


class Ezstream(threading.Thread):

    playing = False

    def __init__(self, alive, filequeue, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'Ezstream Thread'
        self._alive = alive
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
        while self.alive:
            if restart:
                restart = False
                self.playing = False
                logger.warn("%s: Restarting ezstream", self.name)
                ezstream = subprocess.Popen(_ezcmd, stdin=subprocess.PIPE)
            if self.filequeue.empty():
                self.playing = False
                restart = True
                logger.warn('%s: empty queue, pausing for 30s.', self.name)
                time.sleep(30)
                continue
            _fn, _meta = self.filequeue.get()
            if _meta != lastmeta:
                try:
                    if self.__updatemetadata(_meta):
                        lastmeta = _meta
                except requests.exceptions.ConnectionError as msg:
                    logger.warning('Metadata: %s: %s', self.name, msg)
            if ezstream.poll() is not None:
                logger.warning("Ezstream died.")
                restart = True
                continue
            self.playing = True
            with open(_fn, 'rb') as fh:
                logger.debug('%s sending %s', self.name, _fn)
                try:
                    ezstream.stdin.write(fh.read())
                except BrokenPipeError:
                    logger.warn('%s: Broken pipe sending to ezstream.', self.name)
                    restart = True
            try:
                os.unlink(_fn)
            except IOError:
                logger.warn("%s: I/O Erro removing %s", self.name, _fn)
        ezstream.kill()
        logger.info('%s dying', self.name)

    def __updatemetadata(self, _meta):
        if not self.playing:
            logger.debug("%s not updating while not playing", self.name)
            return False
        _params = {
            'mode': 'updinfo',
            'mount': f'/{self.mount}',
            'song': _meta
        }
        _url = f'{self.iceserver}/admin/metadata?{_params}'
        req = requests.get(_url, params=_params, auth=self.auth)
        if 'Metadata update successful' in req.text:
            logger.debug('Metadata updated successfully')
            return True
        else:
            logger.debug('Error updated metadata: %s', req.text.strip())
        return False

    @property
    def alive(self):
        return self._alive.isSet()

    @alive.setter
    def alive(self, _bool):
        if not _bool:
            self._alive.clear()
        else:
            self._alive.set()

    @property
    def streaming(self):
        return self.playing


if __name__ == '__main__':
    from playlist import FipPlaylist
    from fetcher import FipChunks
    logger.setLevel(logging.DEBUG)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    logger.addHandler(streamhandler)
    logging.getLogger("urllib3").setLevel(logging.WARN)
    alive = threading.Event()
    _queue = queue.Queue()
    alive.set()
    pl = FipPlaylist(alive, _queue)
    dl = FipChunks(alive, _queue, ffmpeg='/home/rchiechi/bin/ffmpeg')
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
    ezstreamcast = Ezstream(alive, dl.filequeue,
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
