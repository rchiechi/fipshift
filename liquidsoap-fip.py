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
from fipbuffer import FIPBuffer
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

p = subprocess.run(['which', 'liquidsoap'], capture_output=True)
if p.returncode == 0:
    SOAP = p.stdout.strip()
else:
    print("I could not locate the soap binary in the PATH.")
    sys.exit()

if opts.delay < 30:
    print("The delay is too short to fill the buffer, please try again with a larger delay.")
    sys.exit(1)

if 0 < opts.restart < opts.delay:
    print("Restart delay must be larger than buffer delay.")
    sys.exit(1)

try:
    TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
    SOAPTMPDIR = os.path.join(config['SOAP']['tmpdir'], 'fipshift', 'liquidsoap')
    SOAPTMPFILE = os.path.join(SOAPTMPDIR, 'liquidsoap.log')
    SOAPPLAYLIST = os.path.join(SOAPTMPDIR, 'playlist.txt')
    SOAPCONFIG = os.path.join(SOAPTMPDIR, 'liquid.soap')
except KeyError:
    print("Bad config file, please delete it from %s and try again." % opts.configdir)
    sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

if not os.path.exists(SOAPTMPDIR):
    os.mkdir(SOAPTMPDIR)
cleantmpdir(SOAPTMPDIR)
print("Saving files to %s" % SOAPTMPDIR)

logger = logging.getLogger(__package__)
# NOTE: Setting DEBUG fills log with subprocess ffmpeg output
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
loghandler = logging.FileHandler(os.path.join(TMPDIR,
                                 os.path.basename(sys.argv[0]).split('.')[0]+'.log'))
loghandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(loghandler)

with open(os.path.join(os.path.dirname(
          os.path.realpath(__file__)), 'liquid.soap'), 'rt') as fr:
    rep = {
           '%PLAYLIST%': os.path.basename(SOAPPLAYLIST),
           '%HOST%': config['SOAP']['HOST'],
           '%PORT%': config['SOAP']['PORT'],
           '%PASSWORD%': config['SOAP']['PASSWORD'],
           '%MOUNT%': config['SOAP']['MOUNT'],
           '%LOGFILE%': os.path.basename(SOAPTMPFILE)}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
    with open(SOAPCONFIG, 'wt') as fw:
        fw.write(xml)

logger.info("Starting buffer threads.")
signal.signal(signal.SIGHUP, killbuffer)
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, LOCK, None, TMPDIR, SOAPPLAYLIST)
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

soap_cmd = [SOAP, '-v', os.path.basename(SOAPCONFIG)]

soap = subprocess.Popen(soap_cmd, cwd=SOAPTMPDIR)
logger.info("Started soap with pid %s", soap.pid)
time.sleep(5)


def resumeplayback():
    logger.warning("soap process died")
    played = getplayed(SOAPTMPFILE)
    playlist = getplaylist(SOAPPLAYLIST)
    if played and playlist:
        for _e in enumerate(playlist):
            if _e[1] == played[-1]:
                with LOCK:
                    with open(SOAPPLAYLIST, 'wb') as fh:
                        logger.info("Resuming playback from %s", playlist[_e[0]])
                        for _ogg in playlist[_e[0]:]:
                            if os.path.exists(_ogg):
                                fh.write(_ogg+b'\n')
                            else:
                                logger.warning("%s does not exist, not writing to playlist.", _ogg)
                break
    soap = subprocess.Popen(soap_cmd, cwd=SOAPTMPDIR)
    logger.info("Restarted soap with pid %s.", soap.pid)
    time.sleep(5)
    return soap


try:
    while True:
        if soap.poll() is not None:
            soap = resumeplayback()
            continue
        time.sleep(1)
        played = getplayed(SOAPPLAYLIST)
        if played:
            played.pop()
            for _p in played:
                if os.path.exists(_p):
                    with LOCK:
                        os.unlink(_p)
        if time.time() - epoch > opts.restart and opts.restart > 0:
            logger.warning("\nReached restart timeout, terminating...\n")
            raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    soap.terminate()

except RestartTimeout:
    soap.terminate()
    killbuffer('RESTARTTIMEOUT', None)
    fipbuffer.join()
    os.execv(__file__, sys.argv)

killbuffer('SOAPDIED', None)
fipbuffer.join()
cleantmpdir(TMPDIR)
