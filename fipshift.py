#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import time
import signal
import queue
import subprocess
from argparse import ArgumentTypeError
from fiphifi.util import get_tmpdir, cleantmpdir
from fiphifi.logging import FipFormatter
from fiphifi.playlist import FipPlaylist
from fiphifi.sender import AACStream
from fiphifi.downloader import Downloader
from fiphifi.options import parseopts
from fiphifi.metadata import FIPMetadata, send_metadata
from fiphifi.constants import TSLENGTH
from fiphifi.icecast import IcecastClient  # New import

def create_icecast_client(_c):
    """Create and initialize icecast client"""
    client = IcecastClient(
        host=_c['HOST'],
        port=int(_c['PORT']),
        mount=_c['MOUNT'],
        username=_c['USER'],
        password=_c['PASSWORD']
    )
    client.start()
    return client

def vampstream(_c):
    """Create realtime stream during buffer period"""
    client = create_icecast_client(_c)
    
    # Set up direct streaming from FIP's AAC stream
    def stream_worker():
        import requests
        chunk_size = 8192
        
        while True:
            try:
                response = requests.get(
                    'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance',
                    stream=True
                )
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        if not client.send_data(chunk):
                            break
            except Exception as e:
                logger.error(f"Vamp stream error: {e}")
                time.sleep(1)
                
    thread = threading.Thread(target=stream_worker, daemon=True)
    thread.start()
    return client, thread

def cleanup(*args):
    global CLEAN
    if CLEAN:
        return
    logger.warning("Main thread caught SIGINT, shutting down.")
    ALIVE.clear()
    for child in children:
        logger.info("Joining %s", children[child].name)
        try:
            children[child].join(timeout=30)
            if children[child].is_alive():
                logger.warning("%s refusing to die.", children[child].name)
        except RuntimeError:
            pass
    logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)
    CLEAN = True
    sys.exit()


try:
    opts, config = parseopts()
except ArgumentTypeError as msg:
    print(msg)
    sys.exit()

logger = logging.getLogger(__package__)
_level = logging.INFO
if opts.debug:
    _level = logging.DEBUG
logger.setLevel(_level)

_c = config['USEROPTS']
try:
    TMPDIR = get_tmpdir(_c)
    _ = config['USEROPTS']['FFMPEG']
except KeyError:
    logger.error("Bad config file, delete it from %s and try again.", opts.configdir)
    sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)

cleantmpdir(TMPDIR)

_logfile = os.path.join(TMPDIR, os.path.basename(sys.argv[0]).split('.')[0] + '.log')
loghandler = logging.FileHandler(_logfile)
loghandler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(FipFormatter())
logger.addHandler(streamhandler)
logger.info("Logging to %s", _logfile)
logging.getLogger("urllib3").setLevel(logging.WARN)
logging.getLogger("charset_normalizer").setLevel(logging.WARN)
logger.debug("Debug logging enabled.")
logging.debug("Logging to %s", _logfile)


ABSPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)))

if opts.ffmpeg:
    FFMPEG = opts.ffmpeg
elif os.path.exists(config['USEROPTS']['FFMPEG']):
    FFMPEG = config['USEROPTS']['FFMPEG']
else:
    # We still check for ffmpeg for backward compatibility
    p = subprocess.run(['which', 'ffmpeg'], capture_output=True)
    if p.returncode == 0:
        FFMPEG = p.stdout.strip()
    else:
        logger.warning("ffmpeg not found, using native streaming")
        FFMPEG = None

logger.info('Starting buffer threads.')

CLEAN = False
CACHE = os.path.join(TMPDIR, 'fipshift.cache')
DLDIR = os.path.join(TMPDIR, 'ts')
DLQUEUE = queue.SimpleQueue()
ALIVE = threading.Event()
children = {}

children["playlist"] = FipPlaylist(ALIVE, DLQUEUE, CACHE)
children["downloader"] = Downloader(ALIVE, DLQUEUE, config)
children["metadata"] = FIPMetadata(ALIVE, tmpdir=TMPDIR)
children["sender"] = AACStream(ALIVE, children["playlist"].urlq, opts.delay, config)

ALIVE.set()
children["playlist"].start()
children["downloader"].start()
children["metadata"].start()

signal.signal(signal.SIGINT, cleanup)

logger.info('Starting vamp stream.')

vamp_client, vamp_thread = vampstream(config['USEROPTS'])
try:
    epoch = children["playlist"].history[0][0]
    logger.info("Restarting from cached history")
except IndexError:
    epoch = time.time()
time.sleep(5)

try:
    if not vamp_client.is_connected:
        logger.error("Failed to start stream, probably another process still running.")
        cleanup()
        
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime) / 60 or 1
        if _remains > 60:
            logger.info('(%0.0f%%) Buffering for %0.1f more %s',
                        (children["playlist"].qsize * TSLENGTH / opts.delay)*100,
                        _remains / 60, 'hours' if _remains / 60 > 1 else 'hour')
        else:
            logger.info('(%0.0f%%) Buffering for %0.0f more %s',
                        (children["playlist"].qsize * TSLENGTH / opts.delay)*100,
                        _remains, 'mins' if _remains > 1.9 else 'min')
        time.sleep(60)
        
        # Check vamp stream health
        if not vamp_client.is_connected:
            logger.warning('Restarting vamp stream.')
            vamp_client.stop()
            vamp_thread.join(timeout=1)
            vamp_client, vamp_thread = vampstream(config['USEROPTS'])
            
        send_metadata(f"{config['USEROPTS']['HOST']}:{config['USEROPTS']['PORT']}",
                      config['USEROPTS']['MOUNT'],
                      f"Realtime Stream: T-{_remains:0.0f} minutes",
                      (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD']))
        _runtime = time.time() - epoch
        
except KeyboardInterrupt:
    logger.info("Killing threads")
    vamp_client.stop()
    vamp_thread.join(timeout=1)
    ALIVE.clear()
    for child in children:
        if children[child].is_alive():
            logger.info("Joining %s", children[child].name)
            children[child].join(timeout=30)
    cleantmpdir(TMPDIR)
    sys.exit()
finally:
    vamp_client.stop()
    vamp_thread.join(timeout=1)

children["sender"].start()
logger.info("Started %s", children["sender"].name)
time.sleep(TSLENGTH)  # Wait for buffer to fill
slug = ''
last_slug = ''
last_update = time.time()
try:
    while True:
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
                children["metadata"].jsoncache = _json
                track = _meta.get('track')
                artist = _meta.get('artist')
                album = _meta.get('album')
                logger.info('Updating metadata at %s for %ss', int(_timeidx), int(_meta['endTime'] - _start))
                logger.info(f'Buffer at {(children["playlist"].qsize * TSLENGTH / opts.delay)*100:0.0f}%.')
                break
        if not _meta:
            continue
        if track == 'Le direct' and time.time() - last_update < TSLENGTH:
            slug = last_slug
        else:
            slug = f'"{track}" by {artist} on {album}'
        if slug != last_slug:
            if send_metadata(f"{config['USEROPTS']['HOST']}:{config['USEROPTS']['PORT']}",
                             config['USEROPTS']['MOUNT'],
                             slug,
                             (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD'])):
                last_slug = slug
                last_update = time.time()

except KeyboardInterrupt:
    logger.warning("Caught KeyboardInterrupt.")

except SystemExit:
    logger.warning("Caught SystemExit.")
finally:
    logger.warning("Main thread exiting.")
    cleanup()
