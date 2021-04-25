#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import signal
import queue
import time
import shout
from fipbuffer import FIPBuffer

# pylint: disable=missing-class-docstring, missing-function-docstring


TMPDIR='/tmp/fipshift'
ALIVE = threading.Event()
buffertime = 15*3600 #CET->PST

if len(sys.argv) > 1:
    buffertime = int(sys.argv[1])
if buffertime < 60:
    print("Delay must be more than 60 sec.")
    sys.exit()
if len(sys.argv) > 1:
    TMPDIR = sys.argv[2]

def killbuffer(signum, frame): # pylint: disable=unused-argument
    print("Received %s, killing buffer thread." % signum)
    ALIVE.clear()

def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins

##### MAIN() ######

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
for tmpfn in os.listdir(TMPDIR):
    print("Clearning %s" % os.path.join(TMPDIR,tmpfn))
    os.remove(os.path.join(TMPDIR,tmpfn))

signal.signal(signal.SIGHUP, killbuffer)
fqueue = queue.Queue()
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, fqueue, TMPDIR)
fipbuffer.start()
time.sleep(3)

try:
    while fipbuffer.getruntime() < buffertime:
        _remains = (buffertime - fipbuffer.getruntime())/60
        sys.stdout.write("\rBuffering for %0.0f min. " % _remains)
        sys.stdout.flush()
        time.sleep(10)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    killbuffer('KEYBOARDINTERRUPT', None)
    fipbuffer.join()
    sys.exit()

s = shout.Shout()
print("Using libshout version %s" % shout.version())

s.host = '10.9.8.13'
s.port = 8000
s.user = 'source'
s.password = 'im08en'
s.mount = "/fip.mp3"
s.format = 'mp3'
s.protocol = 'http'
s.name = 'Time-shifted FIP Radio'
s.genre = 'ecletic'
s.url = 'https://www.fip.fr'
s.public = 0
s.audio_info = {shout.SHOUT_AI_SAMPLERATE: '48000',
                shout.SHOUT_AI_CHANNELS: '2',
                shout.SHOUT_AI_BITRATE: '128'}
try:
    s.open()
except shout.ShoutException as msg:
    print("Error connecting to icy server: %s" % str(msg))
    killbuffer('SHOUTERROR',None)
    sys.exit(1)

while not fqueue.empty():
    try:
        _f = fqueue.get(timeout=10)
        fa = _f[1]
        _h, _m = timeinhours( time.time()-_f[0] )
        sys.stdout.write("\rOpening %s (%0.0fh:%0.0fm) \"%s\"  " % (
            fa, _h, _m, _f[2]['track']) )
        sys.stdout.flush()
        with open(fa, 'rb') as fh:
            s.set_metadata({'song': _f[2]['track'],
                            'artist': _f[2]['artist']}) # only 'song' does anything
            nbuf = fh.read(4096)
            while True:
                buf = nbuf
                nbuf = fh.read(4096)
                if len(buf) == 0:
                    break
                s.send(buf)
                s.sync()
        os.remove(os.path.join(TMPDIR, _f[1]))
    except KeyboardInterrupt:
        print("\nCaught SIGINT, exiting.")
        break
    except queue.Empty:
        print("\nQueue is empty, exiting.")

killbuffer('EMPTYQUEUE',None)
fipbuffer.join()
s.close()
