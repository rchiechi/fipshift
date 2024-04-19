#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import time
import subprocess
import queue
from typing_extensions import TypedDict
import json
# import requests  # type: ignore
from fiphifi.util import cleantmpdir, checkcache, writecache, vampstream  # type: ignore
from fiphifi.playlist import FipPlaylist  # type: ignore
from fiphifi.sender import AACStream  # type: ignore
from fiphifi.options import parseopts  # type: ignore
from fiphifi.metadata import FIPMetadata, send_metadata  # type: ignore


# pylint: disable=missing-class-docstring, missing-function-docstring

opts, config = parseopts()
Children = TypedDict('Children', {'playlist': FipPlaylist, 'metadata': FIPMetadata, 'sender': AACStream})
# epoch = time.time()


logger = logging.getLogger(__package__)
if opts.debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

try:
    TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
    _ = config['USEROPTS']['FFMPEG']
except KeyError:
    logger.error("Bad config file, please delete it from %s and try again.", opts.configdir)
    sys.exit(1)

_logfile = os.path.join(TMPDIR, os.path.basename(sys.argv[0]).split('.')[0] + '.log')
loghandler = logging.FileHandler(_logfile)
loghandler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d [%(levelname)s] %(message)s'))
logger.addHandler(streamhandler)
logger.info("Logging to %s", _logfile)
logging.getLogger("urllib3").setLevel(logging.WARN)
logger.debug("Debug logging enabled.")

ABSPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)))


if opts.ffmpeg:
    FFMPEG = opts.ffmpeg
elif os.path.exists(config['USEROPTS']['FFMPEG']):
    FFMPEG = config['USEROPTS']['FFMPEG']
else:
    p = subprocess.run(['which', 'ffmpeg'], capture_output=True)
    if p.returncode == 0:
        FFMPEG = p.stdout.strip()
    else:
        logger.error("I could not locate the ffmpeg binary in the PATH.")
        sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)

logger.info("Starting buffer threads.")

CACHE = os.path.join(TMPDIR, 'fipshift.cache')
ALIVE = threading.Event()
URLQ = queue.Queue()
epoch = checkcache(CACHE, URLQ)

children: Children = {}
children["playlist"] = FipPlaylist(ALIVE, URLQ)
children["metadata"] = FIPMetadata(ALIVE, tmpdir=TMPDIR)
children["sender"] = AACStream(ALIVE, URLQ,
                               delay=opts.delay,
                               tmpdir=TMPDIR,
                               ffmpeg=FFMPEG,
                               tmpidr=TMPDIR,
                               config=config)

ALIVE.set()
children["playlist"].start()
children["metadata"].start()

if not URLQ.empty():
    logger.info('Loaded %s entries from cache.', URLQ.qsize())

logger.info('Starting vamp stream.')
_c = config['USEROPTS']
ffmpeg_proc = vampstream(FFMPEG, _c)
try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime) / 60 or 1
        logger.info('Buffering for %0.0f more minutes', _remains)
        time.sleep(60)
        if ffmpeg_proc.poll() is not None:
            logger.warning('Restarting vamp stream.')
            # ffmpeg_proc = subprocess.Popen(_ffmpegcmd)
            ffmpeg_proc = vampstream(FFMPEG, _c)
        send_metadata(f"{_c['HOST']}:{_c['PORT']}",
                      _c['MOUNT'],
                      f"Realtime Stream: T-{_remains:0.0f} minutes",
                      (_c['USER'], _c['PASSWORD']))
        writecache(CACHE, children["playlist"].history)
        _runtime = time.time() - epoch
except KeyboardInterrupt:
    logger.info("Killing threads")
    ffmpeg_proc.terminate()
    ALIVE.clear()
    for child in children:
        if children[child].is_alive():
            logger.info("Joining %s", children[child].name)
            children[child].join(timeout=30)
    cleantmpdir(TMPDIR)
    sys.exit()
finally:
    ffmpeg_proc.terminate()

children["sender"].start()  # type: ignore
logger.info("Started %s", children["sender"].name)
slug = ''
last_slug = ''
try:
    while True:
        writecache(CACHE, children["playlist"].history)
        time.sleep(1)
        for child in children:
            if not children[child].is_alive():
                logger.error(f"{children[child].name} died, exiting.")
                raise SystemExit
        _start = children["sender"].timestamp
        _json = children["metadata"].jsoncache
        track, artist, album = 'Le song', '¯\\_(ツ)_/¯', 'Le album'
        _meta = {}
        for _timeidx in _json:
            if int(_json[_timeidx]['endTime']) > int(_start) >= int(_timeidx):
                _meta = _json.pop(_timeidx)
                with children["metadata"].lock:
                    with open(children["metadata"].cache, 'wt') as fh:
                        json.dump(_json, fh)
                track = _meta.get('track')
                artist = _meta.get('artist')
                album = _meta.get('album')
                logger.info(f'Updating metadata at {_timeidx}')
                break
        if not _meta:
            continue
        slug = f'"{track}" by {artist} on {album}'
        if slug != last_slug:
            if send_metadata(children["sender"].iceserver,
                             config['USEROPTS']['MOUNT'],
                             slug,
                             (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD'])):
                last_slug = slug

except (KeyboardInterrupt, SystemExit):
    logger.warning("Main thread killed.")

finally:
    ALIVE.clear()
    for child in children:
        logger.info("Joining %s", children[child].name)
        children[child].join(timeout=30)
    _urlz = []
    while not URLQ.empty():
        try:
            _urlz.append(URLQ.get_nowait())
        except queue.Empty:
            break
    writecache(CACHE, _urlz)
    logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)
