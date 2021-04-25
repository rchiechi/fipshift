#!/usr/bin/env python3
'''Time-shift FIP Radio for listening in a different time zone.'''

import os
import sys
import threading
import signal
import queue
import time
import shout
# import eyed3
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

def killbuffer(signum, frame): # pylint: disable=unused-argument
    ALIVE.clear()

def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins

t_start = time.time()

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

try:
    while time.time() - t_start < buffertime:
        _remains = (buffertime - (time.time() - t_start))/60
        sys.stdout.write("\rBuffering for %0.0f min." % _remains)
        sys.stdout.flush()
        time.sleep(60)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    killbuffer(None,None)
    fipbuffer.join()
    sys.exit()

s = shout.Shout()
print("Using libshout version %s" % shout.version())

s.host = '10.9.8.13'
# s.port = 8000
# s.user = 'source'
s.password = 'im08en'
s.mount = "/fip.mp3"
# s.format = 'mp3'
# s.protocol = 'icy'
# s.format = 'vorbis' | 'mp3'
# s.protocol = 'http' | 'xaudiocast' | 'icy'
s.name = 'Time-shifted FIP Radio'
# s.genre = ''
# s.url = ''
s.public = 0

s.audio_info = {shout.SHOUT_AI_SAMPLERATE: '48000',
                shout.SHOUT_AI_CHANNELS: '2',
                shout.SHOUT_AI_BITRATE: '128'}

# s.audio_info = { 'key': 'val', ... }
#  (keys are shout.SHOUT_AI_BITRATE, shout.SHOUT_AI_SAMPLERATE,
#   shout.SHOUT_AI_CHANNELS, shout.SHOUT_AI_QUALITY)
try:
    s.open()
except shout.ShoutException as msg:
    print("Error connecting to icy server: %s" % str(msg))
    killbuffer(None,None)
    sys.exit(1)

total = 0
st = time.time()

while not fqueue.empty():
    try:
        _f = fqueue.get(timeout=10)
        fa = _f[1]
        _h, _m = timeinhours( time.time()-_f[0] )
        sys.stdout.write("\rOpening %s (%0.0fh:%0.0fm)  " % (fa, _h, _m) )
        sys.stdout.flush()
        # _af = eyed3.load(fa)
        # if _af.tag is not None:
        #     print(_af.tag)
        with open(fa, 'rb') as fh:
            #TODO: can we extract this from metadata?
            #s.set_metadata({'song': fa})
            nbuf = fh.read(4096)
            while True:
                buf = nbuf
                nbuf = fh.read(4096)
                total = total + len(buf)
                if len(buf) == 0:
                    break
                s.send(buf)
                s.sync()
        #sys.stdout.write("\rDeleting %s  " % _f[1])
        #sys.stdout.flush()
        os.remove(os.path.join(TMPDIR, _f[1]))
    except KeyboardInterrupt:
        print("Caught SIGINT, exiting.")
        break
    except queue.Empty:
        print("Queue is empty, exiting.")

killbuffer(None,None)
fipbuffer.join()
et = time.time()
br = total*0.008/(et-st)
print("Sent %d bytes in %d seconds (%f kbps)" % (total, et-st, br))
s.close()
