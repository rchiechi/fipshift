#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import logging
import signal
import queue
import time
import subprocess
# import shutil
# import shout
# import pydub
from fipbuffer import FIPBuffer
from options import parseopts

# pylint: disable=missing-class-docstring, missing-function-docstring

class RestartTimeout(Exception):
    def __init__(self,expression,message):
        # Call the base class constructor with the parameters it needs
        super().__init__(expression)

        # Now for your custom code...
        self.errors = message


p = subprocess.run(['which', 'ices'], capture_output=True)
if p.returncode == 0:
    ICES = p.stdout.strip()
else:
    print("I could not locate the ices binary in the PATH.")
    sys.exit()


ALIVE = threading.Event()
LOCK = threading.Lock()

def killbuffer(signum, frame):  # pylint: disable=unused-argument
    print("\nReceived %s, killing buffer thread." % signum)
    ALIVE.clear()
    logger.info("Received %s, killing buffer thread.", signum)

def cleantmpdir(tmpdir):
    n = 0
    for tmpfn in os.listdir(tmpdir):
        if os.path.isdir(os.path.join(tmpdir,tmpfn)):
            sys.stdout.write("\nNot removing directory %s " % os.path.join(tmpdir,tmpfn))
            continue
        sys.stdout.write("\rClearning %s " % os.path.join(tmpdir,tmpfn))
        sys.stdout.flush()
        os.remove(os.path.join(tmpdir,tmpfn))
        n += 1
    print("\033[2K\rCleaned: %s files in %s. " % (n, tmpdir))


def getplayed():
    _played = []
    if not os.path.exists(ICESTMPFILE):
        logger.warning("%s does not exist, cannot parse log.", ICESTMPFILE)
        return _played
    with open(ICESTMPFILE, 'rb') as fh:
        if os.path.getsize(ICESTMPFILE) >= 524288:
            fh.seek(-524288, 2)
        for _l in fh:
            # [2021-09-20  13:44:15] INFO playlist-builtin/playlist_read Currently playing "/tmp/fipshift/ices/0000000000000021"
            if b'Currently playing' in _l:
                _played.append(_l.split(b'"')[-2])
    if not _played:
        logger.warning('Did not find any entries in %s', ICESTMPFILE)
    return _played

def getplaylist():
    _playlist = []
    if not os.path.exists(ICESPLAYLIST):
        logger.warning("%s does not exist, cannot parse playlist.", ICESPLAYLIST)
        return _playlist
    with open(ICESPLAYLIST, 'rb') as fh:
        for _l in fh:
            _playlist.append(_l.strip())
    if not _playlist:
        logger.warning('Did not find any entries in %s', ICESPLAYLIST)
    return _playlist


# # # # # MAIN () # # # # # #


opts, config = parseopts()

if opts.delay < 10:
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
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
loghandler = logging.FileHandler(os.path.join(TMPDIR,
                                 os.path.basename(sys.argv[0]).split('.')[0]+'.log'))
loghandler.setFormatter(logging.Formatter('%(asctime)s %(process)d %(levelname)s %(message)s'))
logger.addHandler(loghandler)

with open(os.path.join(os.path.dirname(
          os.path.realpath(__file__)), 'ices-playlist.xml'), 'rt') as fr:
    xml = fr.read().replace(
        '%ICESTMPDIR%', ICESTMPDIR).replace(
            '%HOST%', config['ICES']['HOST']).replace(
                '%PORT%', config['ICES']['PORT']).replace(
                    '%PASSWORD%', config['ICES']['PASSWORD']).replace(
                        '%MOUNT%', config['ICES']['MOUNT'])
    with open(ICESCONFIG, 'wt') as fw:
        fw.write(xml)

# sys.stdout.write("Writing to %s" % PLAYLIST)
# with open(PLAYLIST, 'wt') as fh:
#     fh.write('\n'.join(FIPBuffer.generateplaylist()))

logger.info("Starting buffer threads.")

signal.signal(signal.SIGHUP, killbuffer)
fqueue = queue.Queue()
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, LOCK, fqueue, TMPDIR, ICESTMPDIR)
fipbuffer.start()
epoch = time.time()
time.sleep(3)

try:
    while fipbuffer.getruntime() < opts.delay:
        _remains = (opts.delay - fipbuffer.getruntime())/60 or 1
        sys.stdout.write("\033[2K\rBuffering for %0.0f min. " % _remains)
        sys.stdout.flush()
        time.sleep(10)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    killbuffer('KEYBOARDINTERRUPT', None)
    fipbuffer.join()
    sys.exit()

ices = subprocess.Popen([ICES, ICESCONFIG])
logger.info("Started ices with pid %s", ices.pid)
time.sleep(5)

def resumeplayback():
    logger.warning("ices process died")
    played = getplayed()
    playlist = getplaylist()
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
    ices = subprocess.Popen([ICES, ICESCONFIG])
    logger.info("Restarted ices with pid %s.", ices.pid)
    time.sleep(5)
    return ices


try:
    while True:
        if ices.poll() is not None:
            ices = resumeplayback()
            continue
        time.sleep(1)
        played = getplayed()
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
    ices.terminate()

except RestartTimeout:
    ices.terminate()
    killbuffer('RESTARTTIMEOUT',None)
    fipbuffer.join()
    os.execv(__file__, sys.argv)

killbuffer('ICESDIED',None)
fipbuffer.join()
cleantmpdir(TMPDIR)
