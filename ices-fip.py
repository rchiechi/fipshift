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

p = subprocess.run(['which', 'ices'], capture_output=True)
if p.returncode == 0:
    ICES = p.stdout.strip()
else:
    print("I could not locate the ices binary in the PATH.")
    sys.exit()

p = subprocess.run([ICES, '-V'], stdout=subprocess.PIPE)
_icesver = float(p.stdout.split(b'\n')[0].split(b' ')[-1])
if _icesver > 1.0:
    print(f"Ices version {_icesver} > 0; Ices 0.x is required for MP3 streaming.")
    sys.exit()

if opts.delay < 30:
    print("The delay is too short to fill the buffer, please try again with a larger delay.")
    sys.exit(1)

if 0 < opts.restart < opts.delay:
    print("Restart delay must be larger than buffer delay.")
    sys.exit(1)

try:
    TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
    ICESTMPDIR = os.path.join(config['ICES']['tmpdir'],'fipshift','ices')
    ICESTMPFILE = os.path.join(ICESTMPDIR, 'ices.log')
    ICESPLAYLIST = os.path.join(ICESTMPDIR,'playlist.txt')
    ICESCONFIG = os.path.join(ICESTMPDIR,'ices-playlist.xml')
except KeyError:
    print("Bad config file, please delete it from %s and try again." % opts.configdir)
    sys.exit(1)

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

if not os.path.exists(ICESTMPDIR):
    os.mkdir(ICESTMPDIR)
cleantmpdir(ICESTMPDIR)
print("Saving files to %s" % ICESTMPDIR)

logger = logging.getLogger(__package__)
# NOTE: Setting DEBUG fills log with subprocess ffmpeg output
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
loghandler = logging.FileHandler(os.path.join(TMPDIR,
                                 os.path.basename(sys.argv[0]).split('.')[0]+'.log'))
loghandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(loghandler)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(streamhandler)

with open(os.path.join(os.path.dirname(
          os.path.realpath(__file__)), 'ices-playlist.xml'), 'rt') as fr:
    rep = {'%ICESTMPDIR%': ICESTMPDIR,
           '%PLAYLIST%': os.path.basename(ICESPLAYLIST),
           '%HOST%': config['ICES']['HOST'],
           '%PORT%': config['ICES']['PORT'],
           '%PASSWORD%': config['ICES']['PASSWORD'],
           '%MOUNT%': config['ICES']['MOUNT']}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    xml = pattern.sub(lambda m: rep[re.escape(m.group(0))], fr.read())
    with open(ICESCONFIG, 'wt') as fw:
        fw.write(xml)

logger.info("Starting buffer threads.")
signal.signal(signal.SIGHUP, killbuffer)
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, LOCK, None, TMPDIR, ICESPLAYLIST)
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

ices_cmd = [ICES, '-c',
            os.path.basename(ICESCONFIG),
            '-P', config['ICES']['PASSWORD'],
            '-h', config['ICES']['HOST'],
            '-p', config['ICES']['PORT']]

ices = subprocess.Popen(ices_cmd, cwd=ICESTMPDIR)
logger.info("Started ices with pid %s", ices.pid)
time.sleep(5)


def resumeplayback():
    logger.warning("ices process died")
    played = getplayed(ICESTMPFILE)
    playlist = getplaylist(ICESPLAYLIST)
    if played and playlist:
        for _e in enumerate(playlist):
            if _e[1] == played[-1]:
                with LOCK:
                    with open(ICESPLAYLIST, 'wb') as fh:
                        logger.info("Resuming playback from %s", playlist[_e[0]])
                        for _ogg in playlist[_e[0]:]:
                            if os.path.exists(_ogg):
                                fh.write(_ogg+b'\n')
                            else:
                                logger.warning("%s does not exist, not writing to playlist.", _ogg)
                break
    ices = subprocess.Popen(ices_cmd, cwd=ICESTMPDIR)
    logger.info("Restarted ices with pid %s.", ices.pid)
    time.sleep(5)
    return ices


try:
    while True:
        if ices.poll() is not None:
            ices = resumeplayback()
            continue
        time.sleep(1)
        played = getplayed(ICESPLAYLIST)
        if played:
            played.pop()
            for _p in played:
                if os.path.exists(_p):
                    with LOCK:
                        os.unlink(_p)
                        _playlist = []
                        with open(ICESPLAYLIST, 'rb') as fh:
                            for _l in fh:
                                if _l != _p:
                                    _playlist.append(_l)
                        with open(ICESPLAYLIST, 'wb') as fh:
                            fh.write(b'\n'.join(_playlist))
                        logger.info('Cleaned %s', os.path.basename(_p))
        if time.time() - epoch > opts.restart and opts.restart > 0:
            logger.warning("\nReached restart timeout, terminating...\n")
            raise(RestartTimeout(None, "Restarting"))

except KeyboardInterrupt:
    ices.terminate()

except RestartTimeout:
    ices.terminate()
    killbuffer('RESTARTTIMEOUT', None)
    fipbuffer.join()
    os.execv(__file__, sys.argv)

killbuffer('ICESDIED', None)
fipbuffer.join()
cleantmpdir(TMPDIR)
