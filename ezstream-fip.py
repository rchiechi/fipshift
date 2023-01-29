#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import signal
import time
import subprocess
import re
from util import RestartTimeout, cleantmpdir, getplayed, getplaylist
from fiphifi import FipPlaylist, FipChunks
from options import parseopts

# pylint: disable=missing-class-docstring, missing-function-docstring

ALIVE = threading.Event()
LOCK = threading.Lock()


def killbuffer(signum, frame):  # pylint: disable=unused-argument
    print("\nReceived %s, killing buffer thread." % signum)
    ALIVE.clear()
    logger.info("Received %s, killing buffer thread.", signum)


# # # # # MAIN () # # # # # #


opts, config = parseopts()

p = subprocess.run(['which', 'ezstream'], capture_output=True)
if p.returncode == 0:
    EZSTREAM = p.stdout.strip()
else:
    print("I could not locate the ezstream binary in the PATH.")
    sys.exit()

p = subprocess.run(['which', 'ffmpeg'], capture_output=True)
if p.returncode == 0:
    FFMPEG = p.stdout.strip()
else:
    print("I could not locate the ffmpeg binary in the PATH.")
    sys.exit()

if opts.delay < 30:
    print("The delay is too short to fill the buffer, please try again with a larger delay.")
    sys.exit(1)

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
loghandler = logging.FileHandler(os.path.join(TMPDIR,
                                 os.path.basename(sys.argv[0]).split('.')[0]+'.log'))
loghandler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(streamhandler)

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
fipbuffer = FIPBuffer(ALIVE, LOCK, None, TMPDIR, EZSTREAMPLAYLIST)
if opts.tag:
    fipbuffer.metadata = True
fipbuffer.start()
epoch = time.time()
time.sleep(3)

try:
    while fipbuffer.getruntime() < opts.delay:
        _remains = (opts.delay - fipbuffer.getruntime())/60 or 1
        # _remains = (opts.delay - fipbuffer.getruntime()) or 1
        sys.stdout.write("\033[2K\rBuffering for %0.0f min. " % _remains)
        sys.stdout.flush()
        time.sleep(10)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.name)
    killbuffer('KEYBOARDINTERRUPT', None)
    fipbuffer.join()
    sys.exit()

ezstream_cmd = [EZSTREAM, '-c',
            os.path.basename(EZSTREAMCONFIG),
            '-P', config['EZSTREAM']['PASSWORD'],
            '-h', config['EZSTREAM']['HOST'],
            '-p', config['EZSTREAM']['PORT']]

ezstream = subprocess.Popen(ezstream_cmd, cwd=EZSTREAMTMPDIR)
logger.info("Started ezstream with pid %s", ezstream.pid)
time.sleep(5)


def resumeplayback():
    logger.warning("ezstream process died")
    played = getplayed(EZSTREAMTMPFILE)
    playlist = getplaylist(EZSTREAMPLAYLIST)
    if played and playlist:
        for _e in enumerate(playlist):
            if _e[1] == played[-1]:
                with LOCK:
                    with open(EZSTREAMPLAYLIST, 'wb') as fh:
                        logger.info("Resuming playback from %s", playlist[_e[0]])
                        for _ogg in playlist[_e[0]:]:
                            if os.path.exists(_ogg):
                                fh.write(_ogg+b'\n')
                            else:
                                logger.warning("%s does not exist, not writing to playlist.", _ogg)
                break
    ezstream = subprocess.Popen(ezstream_cmd, cwd=EZSTREAMTMPDIR)
    logger.info("Restarted ezstream with pid %s.", ezstream.pid)
    time.sleep(5)
    return ezstream


try:
    while True:
        if ezstream.poll() is not None:
            ezstream = resumeplayback()
            continue
        time.sleep(1)
        played = getplayed(os.path.join(EZSTREAMTMPDIR, 'ezstream.log'))
        if len(played) > 1:
            played.pop()
            for _p in played:
                if os.path.exists(_p):
                    with LOCK:
                        os.unlink(_p)
                        _playlist = []
                        with open(EZSTREAMPLAYLIST, 'rb') as fh:
                            for _l in fh:
                                if _l != _p:
                                    _playlist.append(_l)
                        with open(EZSTREAMPLAYLIST, 'wb') as fh:
                            fh.write(b'\n'.join(_playlist))
                        logger.info('Cleaned %s', os.path.basename(_p))
        if time.time() - epoch > opts.restart and opts.restart > 0:
            logger.warning("\nReached restart timeout, terminating...\n")
            raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    ezstream.terminate()

except RestartTimeout:
    ezstream.terminate()
    killbuffer('RESTARTTIMEOUT', None)
    fipbuffer.join()
    os.execv(__file__, sys.argv)

killbuffer('EZSTREAMDIED', None)
fipbuffer.join()
cleantmpdir(TMPDIR)
