#!/usr/bin/env python3

# usage: ./example.py /path/to/file1 /path/to/file2 ...
import os
import sys
import threading
import queue
import time
import shout
from fipbuffer import FIPBuffer

TMPDIR='/tmp/fipshift'
buffertime = 60*60

t_start = time.time()

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
for tmpfn in os.listdir(TMPDIR):
    print("Clearning %s" % os.path.join(TMPDIR,tmpfn))
    os.remove(os.path.join(TMPDIR,tmpfn))

alive = threading.Event()
fqueue = queue.Queue()
alive.set()
fipbuffer = FIPBuffer(alive, fqueue, TMPDIR)
fipbuffer.start()

try:
    while time.time() - t_start < buffertime:
        print("Buffering for %0.0f more seconds." % (buffertime - (time.time() - t_start)) )
        time.sleep(1)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    alive.clear()
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

while True:
    try:
        _f = fqueue.get()
        fa = _f[1]
        print("opening file %s" % fa)
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
        print("Deleting %s" % _f[1])
        os.remove(os.path.join(TMPDIR, _f[1]))
    except KeyboardInterrupt:
        print("Killing %s" % fipbuffer.getName())
        alive.clear()
        fipbuffer.join()
        break
et = time.time()
br = total*0.008/(et-st)
print("Sent %d bytes in %d seconds (%f kbps)" % (total, et-st, br))
s.close()
