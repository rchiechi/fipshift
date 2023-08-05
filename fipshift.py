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
from typing_extensions import TypedDict
# import re
# import shutil
# import datetime
import json
# from tempfile import TemporaryDirectory
import requests  # type: ignore
from fiphifi.util import RestartTimeout, cleantmpdir, killbuffer  # type: ignore
from fiphifi.playlist import FipPlaylist  # type: ignore
# from fiphifi.fetcher import FipChunks  # type: ignore
from fiphifi.sender import AACStream  # type: ignore
from fiphifi.options import parseopts  # type: ignore
from fiphifi.metadata import FIPMetadata  # type: ignore


# pylint: disable=missing-class-docstring, missing-function-docstring

opts, config = parseopts()
Children = TypedDict('Children', {'playlist': FipPlaylist, 'metadata': FIPMetadata, 'sender': AACStream})

try:
    TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
    _ = config['USEROPTS']['FFMPEG']
except KeyError as msg:
    print(msg)
    print("Bad config file, please delete it from %s and try again." % opts.configdir)
    sys.exit(1)

if opts.ffmpeg:
    FFMPEG = opts.ffmpeg
elif os.path.exists(config['USEROPTS']['FFMPEG']):
    FFMPEG = config['USEROPTS']['FFMPEG']
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


if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

logger = logging.getLogger(__package__)
# NOTE: Setting DEBUG fills log with subprocess ffmpeg output
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
_logfile = os.path.join(TMPDIR, os.path.basename(sys.argv[0]).split('.')[0] + '.log')
loghandler = logging.FileHandler(_logfile)
loghandler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(streamhandler)
logger.info("Logging to %s", _logfile)
logging.getLogger("urllib3").setLevel(logging.WARN)

ABSPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)))

logger.info("Starting buffer threads.")

RESTART = False
def restart_threads(signum, frame):
    global RESTART
    logger.warning("Received %s", signum)
    RESTART = True


signal.signal(signal.SIGHUP, restart_threads)
ALIVE = threading.Event()
URLQ = queue.Queue()

children: Children = {}
children["playlist"] = FipPlaylist(ALIVE, URLQ)
children["metadata"] = FIPMetadata(ALIVE, tmpdir=TMPDIR)
children["sender"] = AACStream(ALIVE, URLQ,
                               delay=opts.delay,
                               tmpdir=TMPDIR,
                               ffmpeg=FFMPEG,
                               tmpidr=TMPDIR,
                               # config=config,
                               host=config['USEROPTS']['HOST'],
                               port=config['USEROPTS']['PORT'],
                               mount=config['USEROPTS']['MOUNT'],
                               auth=(config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD']))

ALIVE.set()
children["playlist"].start()
children["metadata"].start()
epoch = time.time()

try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime) / 60 or 1
        logger.info('Buffering for %0.0f more minutes', _remains)
        time.sleep(60)
        _runtime = time.time() - epoch

except KeyboardInterrupt:
    print("Killing threads")
    ALIVE.clear()
    for child in children:
        children[child].join()
    cleantmpdir(TMPDIR)
    sys.exit()

children["sender"].start()  # type: ignore
logger.info("Started %s", children["sender"].name)

try:
    while True:
        time.sleep(1)
        _start = children["sender"].timestamp
        _json = children["metadata"].jsoncache
        track, artist, album = 'Le track', 'Le artist', 'Le album'
        _meta = {}
        for _key in _json:
            logger.debug('Checking %0.0f > %0.0f > %0.0f', _json[_key]['endTime'], _start, _key)
            if int(_json[_key]['endTime']) > int(_start) > int(_key):
                _meta = _json.pop(_key)
                with children["metadata"].lock:  # type: ignore
                    with open(children["metadata"].cache, 'wt') as fh:  # type: ignore
                        json.dump(_json, fh)
                try:
                    track = _meta['track']
                except (KeyError, TypeError):
                    print(_meta)
                try:
                    artist = _meta['artist']
                except (KeyError, TypeError):
                    print(_meta)
                try:
                    album = _meta['album']
                except (KeyError, TypeError):
                    print(_meta)
                break
        if not _meta:
            # logger.debug('No metadata matched for %s', _start)
            continue
        _url = children["sender"].iceserver  # type: ignore
        _params = {'mode': 'updinfo',
                   'mount': f"/{config['USEROPTS']['MOUNT']}",
                   'song': f'{track} - {artist} - {album}'
                   }
        req = requests.get(_url, params=_params,
                           auth=requests.auth.HTTPBasicAuth('source', config['USEROPTS']['PASSWORD']))
        if 'Metadata update successful' in req.text:
            logger.debug('Metadata updated successfully')
        logger.debug("Delay: %s / Offset: %s", children["sender"].offset, opts.delay)  # type: ignore

except (KeyboardInterrupt, SystemExit):
    ALIVE.clear()
    for child in children:
        print(f"Joining {child}")
        children[child].join()

except RestartTimeout:
    killbuffer('RestartTimeout', None)
    os.execv(__file__, sys.argv)

cleantmpdir(TMPDIR)
