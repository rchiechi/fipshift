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
from util import RestartTimeout, cleantmpdir
from fiphifi import FipPlaylist, FipChunks, Ezstream
from options import parseopts

# pylint: disable=missing-class-docstring, missing-function-docstring

ALIVE = threading.Event()


def killbuffer(signum, frame):  # pylint: disable=unused-argument
    print("\nReceived %s, killing buffer thread." % signum)
    ALIVE.clear()
    logger.info("Received %s, killing buffer thread.", signum)
    for _thread in threading.enumerate():
        if _thread != threading.main_thread():
            _thread.join()


# # # # # MAIN () # # # # # #


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
signal.signal(signal.SIGHUP, killbuffer)
ALIVE.set()
pl_queue = queue.Queue()
mp3_queue = queue.Queue()
pl = FipPlaylist(ALIVE, pl_queue)
dl = FipChunks(ALIVE, pl_queue, mp3_queue=mp3_queue, ffmpeg=FFMPEG, tmpdir=TMPDIR)
ezstreamcast = Ezstream(ALIVE, mp3_queue,
                        tmpdir=EZSTREAMTMPDIR,
                        auth=('source', config['EZSTREAM']['PASSWORD'])
                        )
pl.start()
dl.start()
epoch = time.time()
time.sleep(3)

try:
    _runtime = time.time() - epoch
    while _runtime < opts.delay:
        _remains = (opts.delay - _runtime)/60 or 1
        sys.stdout.write("\033[2K\rBuffering for %0.0f min. " % _remains)
        sys.stdout.flush()
        time.sleep(10)
        _runtime = time.time() - epoch
        if dl.lastupdate > 30:
            logger.warn('FipChunks thread is stuck, attempting restart.')
            dl.kill()
            dl = FipChunks(ALIVE, pl_queue, mp3_queue=mp3_queue, ffmpeg=FFMPEG, tmpdir=TMPDIR)
            dl.start()
except KeyboardInterrupt:
    print("Killing %s" % ezstreamcast.name)
    killbuffer('KEYBOARDINTERRUPT', None)
    sys.exit()

ezstreamcast.start()
logger.info("Started %s", ezstreamcast.name)
time.sleep(5)
dl_restarts = 0

try:
    while True:
        for _thread in threading.enumerate():
            if not _thread.is_alive():
                logger.warning("%s is dead!", _thread.name)
        if dl.lastupdate > 30:
            logger.warn('%s is stuck, attempting restart.', dl.name)
            dl.kill()
            dl = FipChunks(ALIVE, pl_queue, mp3_queue=mp3_queue, ffmpeg=FFMPEG, tmpdir=TMPDIR)
            dl.start()
            dl_restarts += 1
        if dl_restarts > 10:
            logger.error('Cannot restart %s, attempting to restart %s', dl.name, __file__)
            killbuffer('RESTARTTIMEOUT', None)
            os.execv(__file__, sys.argv)
        time.sleep(1)
        if time.time() - epoch > opts.restart and opts.restart > 0:
            logger.warning("\nReached restart timeout, terminating...\n")
            raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    killbuffer('KEYBOARDINTERRUPT', None)

except RestartTimeout:
    killbuffer('RESTARTTIMEOUT', None)
    os.execv(__file__, sys.argv)

killbuffer('EZSTREAMDIED', None)
cleantmpdir(TMPDIR)
