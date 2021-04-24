#!/usr/bin/env python3

# usage: ./example.py /path/to/file1 /path/to/file2 ...
import os
import sys
import threading
import signal
import queue
import time
import shout
from fipbuffer import FIPBuffer

TMPDIR='/tmp/fipshift'
ALIVE = threading.Event()
buffertime = 60*60

def killbuffer(signum, frame):
    ALIVE.clear()

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
        print("Buffering for %0.0f more minutes." % (buffertime - (time.time() - t_start))/60 )
        time.sleep(60)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    killbuffer(None,None)
    fipbuffer.join()
    sys.exit()

s = shout.Shout()
print("Using libshout version %s" % shout.version())

s.host = '10.9.8.4'
# s.port = 8000
# s.user = 'source'
s.password = 'im08en'
s.mount = "/fip.mp3"
s.format = 'mp3'
# s.format = 'vorbis' | 'mp3'
# s.protocol = 'http' | 'xaudiocast' | 'icy'
s.name = 'Time-shifted FIP Radio'
# s.genre = ''
# s.url = ''
s.public = 0 

# s.audio_info = { 'key': 'val', ... }
#  (keys are shout.SHOUT_AI_BITRATE, shout.SHOUT_AI_SAMPLERATE,
#   shout.SHOUT_AI_CHANNELS, shout.SHOUT_AI_QUALITY)
s.open()

total = 0
st = time.time()

while not fqueue.empty():
    try:
        _f = fqueue.get(timeout=10)
        fa = _f[1]
        sys.stdout.write("\rOpening %s                " % fa)
        sys.stdout.flush()
        with open(fa, 'rb') as fh:
            #TODO: can we extract this from metadata?
            s.set_metadata({'song': fa})
            nbuf = fh.read(4096)
            while True:
                buf = nbuf
                nbuf = fh.read(4096)
                total = total + len(buf)
                if len(buf) == 0:
                    break
                s.send(buf)
                s.sync()
        sys.stdout.write("\rDeleting %s                " % _f[1])
        sys.stdout.flush()
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

