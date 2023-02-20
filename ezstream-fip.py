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
from fiphifi.util import RestartTimeout, cleantmpdir, killbuffer
from fiphifi.playlist import FipPlaylist
from fiphifi.fetcher import FipChunks
from fiphifi.sender import Ezstream
from fiphifi.options import parseopts

# pylint: disable=missing-class-docstring, missing-function-docstring

opts, config = parseopts()

if opts.ezstream:
    EZSTREAM = opts.ezstream
else:
    p = subprocess.run(['which', 'ezstream'], capture_output=True)
    if p.returncode == 0:
        EZSTREAM = p.stdout.strip()
    else:
        print("I could not locate the ezstream binary in the PATH.")
        sys.exit()

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
    EZSTREAMTMPDIR = os.path.join(config['EZSTREAM']['tmpdir'], 'fipshift', 'ezstream')
    EZSTREAMTMPFILE = os.path.join(EZSTREAMTMPDIR, 'ezstream.log')
    EZSTREAMCONFIG = os.path.join(EZSTREAMTMPDIR, 'ezstream.xml')
except KeyError:
    print("Bad config file, please delete it from %s and try again." % opts.configdir)
    sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

if not os.path.exists(EZSTREAMTMPDIR):
    os.mkdir(EZSTREAMTMPDIR)
cleantmpdir(EZSTREAMTMPDIR)
print("Saving files to %s" % EZSTREAMTMPDIR)

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

with open(os.path.join(os.path.dirname(
          os.path.realpath(__file__)), 'ezstream.xml'), 'rt') as fr:
    rep = {'%HOST%': config['EZSTREAM']['HOST'],
           '%PORT%': config['EZSTREAM']['PORT'],
           '%PASSWORD%': config['EZSTREAM']['PASSWORD'],
           '%MOUNT%': config['EZSTREAM']['MOUNT']}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
    with open(EZSTREAMCONFIG, 'wt') as fw:
        fw.write(xml)

logger.info("Starting buffer threads.")

RESTART = False
def restart_threads(signum, frame):
    global RESTART
    logger.warning("Received %s", signum)
    RESTART = True


signal.signal(signal.SIGHUP, restart_threads)

children = {"playlist": {"queue": queue.Queue(), "alive": threading.Event(), "restarts": 0},
            "fetcher": {"queue": queue.Queue(), "alive": threading.Event(), "restarts": 0},
            "sender": {"alive": threading.Event(), "restarts": 0}
            }

children["playlist"]["thread"] = FipPlaylist(children["playlist"]["alive"],
                                             children["playlist"]["queue"])
children["fetcher"]["thread"] = FipChunks(children["fetcher"]["alive"],
                                          children["playlist"]["queue"],
                                          mp3_queue=children["fetcher"]["queue"],
                                          ffmpeg=FFMPEG, tmpdir=TMPDIR, tag=opts.tag, delay=opts.delay)
children["sender"]["thread"] = Ezstream(children["sender"]["alive"],
                                        children["fetcher"]["queue"],
                                        tmpdir=EZSTREAMTMPDIR,
                                        auth=('source', config['EZSTREAM']['PASSWORD']))

for _child in children:
    children[_child]["alive"].set()

children["playlist"]["thread"].start()
while children["playlist"]["queue"].empty():
    time.sleep(1)
children["fetcher"]["thread"].start()
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

children["sender"]["thread"].start()
logger.info("Started %s", children["sender"]["thread"].name)
time.sleep(5)

try:
    while True:
        for child in ("fetcher", "playlist"):
            if not RESTART:
                if children[child]["thread"].lastupdate < 30:
                    continue
            RESTART = False
            logger.warning('Attempting restart %s.', children[child]["thread"].name)
            children[child]["alive"].clear()
            children[child]["thread"].join(60)
            if child == "fetcher":
                children[child]["thread"] = FipChunks(children[child]["alive"],
                                                        children["playlist"]["queue"],
                                                        mp3_queue=children["fetcher"]["queue"],
                                                        ffmpeg=FFMPEG, tmpdir=TMPDIR, tag=opts.tag, delay=opts.delay)
            if child == "playlist":
                children[child]["thread"] = FipPlaylist(children[child]["alive"],
                                            children["playlist"]["queue"])
            children[child]["alive"].set()
            children[child]["thread"].start()
            children[child]["restarts"] += 1
        if children[child]["restarts"] > 10:
            logger.error('Cannot restart %s, attempting to restart %s', children[child]["thread"].name, __file__)
            killbuffer('RESTARTTIMEOUT', None)
            os.execv(__file__, sys.argv)
        time.sleep(1)
        if time.time() - epoch > opts.restart and opts.restart > 0:
            logger.warning("\nReached restart timeout, terminating...\n")
            raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    killbuffer('KeyboardInterrupt', None)

except SystemExit:
    killbuffer('SystemExit', None)
    cleantmpdir(TMPDIR)
    os.exit()

except RestartTimeout:
    killbuffer('RestartTimeout', None)
    os.execv(__file__, sys.argv)

cleantmpdir(TMPDIR)