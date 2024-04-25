#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import time
import subprocess
import queue
import json
import signal
from fiphifi.util import cleantmpdir, checkcache, writecache, vampstream
from fiphifi.playlist import FipPlaylist
from fiphifi.sender import AACStream
from fiphifi.options import parseopts
from fiphifi.metadata import FIPMetadata, send_metadata
from fiphifi.constants import TSLENGTH


opts, config = parseopts()
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

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)

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


logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)

logger.info("Starting buffer threads.")

CLEAN = False
CACHE = os.path.join(TMPDIR, 'fipshift.cache')
ALIVE = threading.Event()
URLQ = queue.Queue()
epoch = checkcache(CACHE, URLQ)
children = {}

def cleanup(*args):
    global CLEAN
    if CLEAN:
        sys.exit()
    ALIVE.clear()
    for child in children:
        logger.info("Joining %s", children[child].name)
        try:
            children[child].join(timeout=30)
            if children[child].is_alive():
                logger.warning("%s refusing to die.", children[child].name)
        except RuntimeError:
            pass
    _urlz = []
    _qsize = URLQ.qsize()
    logger.info("Caching urls")
    while not URLQ.empty():
        try:
            _urlz.append(URLQ.get_nowait())
        except queue.Empty:
            break
    if len(_urlz) == _qsize:
        writecache(CACHE, _urlz)
        logger.info("Cached %s urls.", len(_urlz))
    else:
        logger.error("Could not cache entire queue %s/%s", len(_urlz), _qsize)
    logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)
    CLEAN = True
    sys.exit()


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

signal.signal(signal.SIGINT, cleanup)

logger.info('Starting vamp stream.')
_c = config['USEROPTS']
ffmpeg_proc = vampstream(FFMPEG, _c)
try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime) / 60 or 1
        if _remains > 60:
            logger.info('(%0.0f%%) Buffering for %0.1f more %s',
                        (URLQ.qsize() * TSLENGTH / opts.delay)*100,
                        _remains / 60, 'hours' if _remains / 60 > 1 else 'hour')
        else:
            logger.info('(%0.0f%%) Buffering for %0.0f more %s',
                        (URLQ.qsize() * TSLENGTH / opts.delay)*100,
                        _remains, 'mins' if _remains > 1.9 else 'min')
        time.sleep(60)
        if ffmpeg_proc.poll() is not None:
            logger.warning('Restarting vamp stream.')
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
    time.sleep(1)
    if ffmpeg_proc.returncode is None:
        ffmpeg_proc.kill()

children["sender"].start()
logger.info("Started %s", children["sender"].name)
time.sleep(TSLENGTH)  # Wait for buffer to fill
slug = ''
last_slug = ''
last_update = time.time()
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
        track, artist, album = 'Le song', r'¯\_(ツ)_/¯', 'Le album'
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
                logger.info(f'Buffer at {(URLQ.qsize() * TSLENGTH / opts.delay)*100:0.0f}%.')
                break
        if not _meta:
            continue
        if track == 'Le direct' and time.time() - last_update < TSLENGTH:
            slug = last_slug
        else:
            slug = f'"{track}" by {artist} on {album}'
        if slug != last_slug:
            if send_metadata(children["sender"].iceserver,
                             config['USEROPTS']['MOUNT'],
                             slug,
                             (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD'])):
                last_slug = slug
                last_update = time.time()

except (KeyboardInterrupt, SystemExit):
    logger.warning("Main thread killed.")

finally:
    cleanup()
