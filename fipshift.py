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
from fiphifi.util import cleantmpdir  # type: ignore
from fiphifi.playlist import FipPlaylist  # type: ignore
from fiphifi.sender import AACStream  # type: ignore
from fiphifi.options import parseopts  # type: ignore
from fiphifi.metadata import FIPMetadata, send_metadata  # type: ignore


# pylint: disable=missing-class-docstring, missing-function-docstring

opts, config = parseopts()
Children = TypedDict('Children', {'playlist': FipPlaylist, 'metadata': FIPMetadata, 'sender': AACStream})
epoch = time.time()


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
                               config=config)
ALIVE.set()
children["playlist"].start()
children["metadata"].start()

logger.info('Starting vamp stream.')

_c = config['USEROPTS']
_ffmpegcmd = [FFMPEG,
              '-loglevel', 'fatal',
              '-re',
              '-i', 'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance',
              '-content_type', 'audio/aac',
              '-ice_name', 'FipShift',
              '-ice_description', 'Time-shifted FIP stream',
              '-ice_genre', 'Eclectic',
              '-c:a', 'copy',
              '-f', 'adts',
              f"icecast://{_c['USER']}:{_c['PASSWORD']}@{_c['HOST']}:{_c['PORT']}/{_c['MOUNT']}"]
ffmpeg_proc = subprocess.Popen(_ffmpegcmd)
time.sleep(1)

try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime) / 60 or 1
        logger.info('Buffering for %0.0f more minutes', _remains)
        send_metadata(f"{_c['HOST']}:{_c['PORT']}",
                      _c['MOUNT'],
                      f"Realtime Stream: T-{_remains:0.0f} minutes",
                      (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD']))
        time.sleep(60)
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

ffmpeg_proc.terminate()
children["sender"].start()  # type: ignore
logger.info("Started %s", children["sender"].name)
slug = ''
last_slug = ''
try:
    while True:
        time.sleep(1)
        _start = children["sender"].timestamp
        _json = children["metadata"].jsoncache
        track, artist, album = 'Le track', 'Le artist', 'Le album'
        _meta = {}
        for _key in _json:
            if int(_json[_key]['endTime']) > int(_start) > int(_key):
                _meta = _json.pop(_key)
                with children["metadata"].lock:
                    with open(children["metadata"].cache, 'wt') as fh:
                        json.dump(_json, fh)
                try:
                    track = _meta['track']
                except (KeyError, TypeError):
                    pass
                try:
                    artist = _meta['artist']
                except (KeyError, TypeError):
                    pass
                try:
                    album = _meta['album']
                except (KeyError, TypeError):
                    pass
                break
        if not _meta:
            continue
        slug = f'"{track}" by {artist} on {album}'
        if slug == last_slug:
            continue
        if send_metadata(children["sender"].iceserver,
                         config['USEROPTS']['MOUNT'],
                         slug,
                         (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD'])):
            last_slug = slug
        # _url = children["sender"].iceserver
        # _params = {'mode': 'updinfo',
        #            'mount': f"/{config['USEROPTS']['MOUNT']}",
        #            'song': slug}
        # req = requests.get(f'http://{_url}/admin/metadata', params=_params,
        #                    auth=requests.auth.HTTPBasicAuth('source', config['USEROPTS']['PASSWORD']))
        # if 'Metadata update successful' in req.text:
        #     logger.info('Metadata udpate: %s', slug)
        #     last_slug = slug
        # else:
        #     logger.warning('Error updating metdata: %s', req.text)

except (KeyboardInterrupt, SystemExit):
    logger.warning("Main thread killed.")

finally:
    ALIVE.clear()
    for child in children:
        logger.info("Joining %s", children[child].name)
        children[child].join(timeout=60)

logger.debug("Cleaned %s files in %s.", cleantmpdir(TMPDIR), TMPDIR)