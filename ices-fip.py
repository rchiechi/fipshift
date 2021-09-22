#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
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

p = subprocess.run(['which', 'ices'], capture_output=True)
if p.returncode == 0:
    ICES = p.stdout.strip()
else:
    print("I could not locate the ices binary in the PATH.")
    sys.exit()


ALIVE = threading.Event()

def killbuffer(signum, frame):  # pylint: disable=unused-argument
    print("\nReceived %s, killing buffer thread." % signum)
    ALIVE.clear()

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


# # # # # MAIN () # # # # # #


opts, config = parseopts()

if opts.delay < 10:
    print("The delay is too short to fill the buffer, please try again with a larger delay.")
    sys.exit()

ICESTMPDIR = os.path.join(config['ICES']['tmpdir'],'fipshift','ices')
TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')
ICESPLAYLIST = os.path.join(ICESTMPDIR,'playlist.txt')
ICESCONFIG = os.path.join(ICESTMPDIR,'ices-playlist.xml')

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
cleantmpdir(TMPDIR)

if not os.path.exists(ICESTMPDIR):
    os.mkdir(ICESTMPDIR)
cleantmpdir(ICESTMPDIR)
print("Saving files to %s" % ICESTMPDIR)

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

signal.signal(signal.SIGHUP, killbuffer)
fqueue = queue.Queue()
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, fqueue, TMPDIR, ICESTMPDIR)
fipbuffer.start()
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

try:
    while True:
        if ices.poll() is None:
            ices = subprocess.Popen([ICES, ICESCONFIG])
            time.sleep(1)
        played = []
        with open(ICESPLAYLIST, 'rb') as fh:
            if os.path.getsize(ICESPLAYLIST) >= 524288:
                fh.seek(-524288, 2)
            for _l in fh:
                # [2021-09-20  13:44:15] INFO playlist-builtin/playlist_read Currently playing "/tmp/fipshift/ices/0000000000000021"
                if b'Currently playing' in _l:
                    played.append(_l.split(b'"')[-2])
        if played:
            played.pop()
            for _p in played:
                if os.path.exists(_p):
                    os.unlink(_p)
        time.sleep(1)
except KeyboardInterrupt:
    ices.terminate()

killbuffer('ICESDIED',None)
fipbuffer.join()
cleantmpdir(TMPDIR)
