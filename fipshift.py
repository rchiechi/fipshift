#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import signal
import time
import subprocess
import queue
import re
import shutil
import datetime
import json
from tempfile import TemporaryDirectory
import requests  # type: ignore
from fiphifi.util import RestartTimeout, cleantmpdir, killbuffer  # type: ignore
from fiphifi.playlist import FipPlaylist  # type: ignore
from fiphifi.fetcher import FipChunks  # type: ignore
from fiphifi.sender import AACStream  # type: ignore
from fiphifi.options import parseopts  # type: ignore
from fiphifi.metadata import FIPMetadata  # type: ignore


# pylint: disable=missing-class-docstring, missing-function-docstring

opts, config = parseopts()

# if opts.ezstream:
#     EZSTREAM = opts.ezstream
# else:
#     p = subprocess.run(['which', 'ezstream'], capture_output=True)
#     if p.returncode == 0:
#         EZSTREAM = p.stdout.strip()
#     else:
#         print("I could not locate the ezstream binary in the PATH.")
#         sys.exit()

if opts.ffmpeg:
    FFMPEG = opts.ffmpeg
else:
    p = subprocess.run(['which', 'ffmpeg'], capture_output=True)
    if p.returncode == 0:
        FFMPEG = p.stdout.strip()
    else:
        print("I could not locate the ffmpeg binary in the PATH.")
        sys.exit()

if 0 < opts.restart < opts.delay:
    print("Restart delay must be larger than buffer delay.")
    sys.exit(1)

try:
    TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
    # EZSTREAMTMPDIR = os.path.join(config['EZSTREAM']['tmpdir'], 'fipshift', 'ezstream')
    # EZSTREAMTMPFILE = os.path.join(EZSTREAMTMPDIR, 'ezstream.log')
    # EZSTREAMCONFIG = os.path.join(EZSTREAMTMPDIR, 'ezstream.xml')
except KeyError as msg:
    print(msg)
    print("Bad config file, please delete it from %s and try again." % opts.configdir)
    sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

# if not os.path.exists(EZSTREAMTMPDIR):
#     os.mkdir(EZSTREAMTMPDIR)
# cleantmpdir(EZSTREAMTMPDIR)
# print("Saving files to %s" % EZSTREAMTMPDIR)

logger = logging.getLogger(__package__)
# NOTE: Setting DEBUG fills log with subprocess ffmpeg output
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
_logfile = os.path.join(TMPDIR, os.path.basename(sys.argv[0]).split('.')[0]+'.log')
loghandler = logging.FileHandler(_logfile)
loghandler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(streamhandler)
logger.info("Logging to %s", _logfile)

ABSPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)))
# with open(os.path.join(ABSPATH, 'ezstream.xml'), 'rt') as fr:
#     rep = {'%HOST%': config['EZSTREAM']['HOST'],
#            '%PORT%': config['EZSTREAM']['PORT'],
#            '%PASSWORD%': config['EZSTREAM']['PASSWORD'],
#            '%MOUNT%': config['EZSTREAM']['MOUNT']}
#     rep = dict((re.escape(k), v) for k, v in rep.items())
#     pattern = re.compile("|".join(rep.keys()))
#     xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
#     with open(EZSTREAMCONFIG, 'wt') as fw:
#         fw.write(xml)
# shutil.copy(os.path.join(ABSPATH, 'silence.mp3'), os.path.join(EZSTREAMTMPDIR, 'silence.mp3'))
logger.info("Starting buffer threads.")

RESTART = False
def restart_threads(signum, frame):
    global RESTART
    logger.warning("Received %s", signum)
    RESTART = True


signal.signal(signal.SIGHUP, restart_threads)

children = {"playlist": {"queue": queue.Queue(), "alive": threading.Event(), "restarts": 0},
            "metadata": {"alive": threading.Event(), "restarts": 0},
            "sender": {"alive": threading.Event(), "restarts": 0}
            }

children["playlist"]["thread"] = FipPlaylist(children["playlist"]["alive"],
                                             children["playlist"]["queue"])
children["metadata"]["thread"] = FIPMetadata(children["metadata"]["alive"],
                                             tmpdir=TMPDIR)
children["sender"]["thread"] = AACStream(children["sender"]["alive"],
                                         children["playlist"]["queue"],
                                         tmpdir=TMPDIR,
                                         ffmpeg=config['USEROPTS']['FFMPEG'],
                                         host=config['USEROPTS']['HOST'],
                                         port=config['USEROPTS']['PORT'],
                                         mount=config['USEROPTS']['MOUNT'],
                                         auth=(config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD']))

for child in children:
    children[child]["alive"].set()  # type: ignore

children["playlist"]["thread"].start()  # type: ignore
children["metadata"]["thread"].start()  # type: ignore
epoch = time.time()

try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime)/60 or 1
        logger.info('Buffering for %0.0f more minutes', _remains)
        time.sleep(10)
        _runtime = time.time() - epoch

except KeyboardInterrupt:
    print("Killing threads")
    killbuffer('KeyboardInterrupt', None)
    cleantmpdir(TMPDIR)
    sys.exit()

children["sender"]["thread"].start()  # type: ignore
logger.info("Started %s", children["sender"]["thread"].name)  # type: ignore
time.sleep(5)

try:
    while True:
        time.sleep(1)
        _start = children["sender"]["thread"].timestamp  # type: ignore
        _json = children["metadata"]["thread"].jsoncache  # type: ignore
        track, artist, album = 'Le track', 'Le artist', 'Le album'
        _meta = {}
        for _key in _json:
            if _json[_key]['endTime'] > _start > _key:
                _meta = _json.pop(_key)
                with children["metadata"]["thread"].lock:  # type: ignore
                    with open(children["metadata"]["thread"].cache, 'wt') as fh:  # type: ignore
                        json.dump(_json, fh)
                try:
                    track = _meta['firstLine']['title']
                except TypeError:
                    pass
                try:
                    artist = _meta['secondLine']['title']
                except TypeError:
                    pass
                try:
                    album = _meta['release']['title']
                except TypeError:
                    pass
        if not _meta:
            continue
        _url = children["sender"]["thread"].iceserver  # type: ignore
        _params = {'mode': 'updinfo',
                   'mount': f"/{config['USEROPTS']['MOUNT']}",
                   'song': f'{track} - {artist} - {album}'
                   }
        req = requests.get(_url, params=_params,
                           auth=requests.auth.HTTPBasicAuth('source', config['USEROPTS']['PASSWORD']))
        if 'Metadata update successful' in req.text:
            logger.debug('Metadata updated successfully')
        #     def __updatemetadata(self, _meta):
        #         if not self.playing:
        #             logger.debug("%s not updating while not playing", self.name)
        #             return False
        #         _params = {
        #             'mode': 'updinfo',
        #             'mount': f'/{self.mount}',
        #             'song': _meta
        #         }
        #         _url = f'{self.iceserver}/admin/metadata?{_params}'
        #         req = requests.get(_url, params=_params, auth=self.auth)
        #         if 'Metadata update successful' in req.text:
        #             logger.debug('Metadata updated successfully')
        #             return True
        #         else:
        #             logger.debug('Error updated metadata: %s', req.text.strip())
        #         return False
        
        # for child in ("fetcher", "playlist"):
        #     if not RESTART:
        #         if children["playlist"]["thread"].lastupdate < 30:  # type: ignore
        #             continue
        #     RESTART = False
        #     logger.warning('Attempting restart %s.', children[child]["thread"].name)  # type: ignore
        #     children[child]["alive"].clear()  # type: ignore
        #     children[child]["thread"].join(60)  # type: ignore
        #     # if child == "fetcher":
        #     #     children[child]["thread"] = FipChunks(children[child]["alive"],
        #     #                                             children["playlist"]["queue"],
        #     #                                             mp3_queue=children["fetcher"]["queue"],
        #     #                                             ffmpeg=FFMPEG, tmpdir=TMPDIR, tag=opts.tag, delay=opts.delay)
        #     if child == "playlist":
        #         children[child]["thread"] = FipPlaylist(children[child]["alive"],
        #                                     children["playlist"]["queue"])
        #     children[child]["alive"].set()  # type: ignore
        #     children[child]["thread"].start()  # type: ignore
        #     children[child]["restarts"] += 1  # type: ignore
        # if children[child]["restarts"] > 10:  # type: ignore
        #     logger.error('Cannot restart %s, attempting to restart %s', children[child]["thread"].name, __file__)  # type: ignore
        #     killbuffer('RESTARTTIMEOUT', None)
        #     os.execv(__file__, sys.argv)
        # time.sleep(1)
        # if time.time() - epoch > opts.restart and opts.restart > 0:
        #     logger.warning("\nReached restart timeout, terminating...\n")
        #     raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    killbuffer('KeyboardInterrupt', None)

except SystemExit:
    killbuffer('SystemExit', None)
    cleantmpdir(TMPDIR)
    sys.exit()

except RestartTimeout:
    killbuffer('RestartTimeout', None)
    os.execv(__file__, sys.argv)

cleantmpdir(TMPDIR)