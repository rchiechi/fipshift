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
from options import parseopts

# pylint: disable=missing-class-docstring, missing-function-docstring

ALIVE = threading.Event()

def killbuffer(signum, frame):  # pylint: disable=unused-argument
    print("\nReceived %s, killing buffer thread." % signum)
    ALIVE.clear()

def cleantmpdir(tmpdir):
    n = 0
    for tmpfn in os.listdir(tmpdir):
        sys.stdout.write("\rClearning %s " % os.path.join(tmpdir,tmpfn))
        sys.stdout.flush()
        os.remove(os.path.join(tmpdir,tmpfn))
        n += 1
    print("\033[2K\rCleaned: %s files. " % n)

def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins

# # # # # MAIN () # # # # # #


opts, config = parseopts()

if opts.delay < 10:
    print("The delay is too short to fill the buffer, please try again with a larger delay.")
    sys.exit()

TMPDIR = os.path.join(config['USEROPTS']['TMPDIR'], 'fipshift')

if not os.path.exists(TMPDIR):
    os.mkdir(TMPDIR)
print("Saving files to %s" % TMPDIR)
cleantmpdir(TMPDIR)

signal.signal(signal.SIGHUP, killbuffer)
fqueue = queue.Queue()
ALIVE.set()
fipbuffer = FIPBuffer(ALIVE, fqueue, TMPDIR)
fipbuffer.start()
time.sleep(3)

s = shout.Shout()
print("Using libshout version %s" % shout.version())

s.host = config['USEROPTS']['HOST']
s.port = int(config['USEROPTS']['PORT'])
s.user = config['USEROPTS']['USER']
s.password = config['USEROPTS']['PASSWORD']
s.mount = config['USEROPTS']['MOUNT']
s.name = config['USEROPTS']['NAME']
s.genre = config['USEROPTS']['GENRE']
s.url = config['USEROPTS']['URL']
s.public = int(config['USEROPTS']['PUBLIC'])
s.format = 'mp3'
s.protocol = 'http'
s.audio_info = {shout.SHOUT_AI_SAMPLERATE: '48000',
                shout.SHOUT_AI_CHANNELS: '2',
                shout.SHOUT_AI_BITRATE: '128'}
try:
    print("Starting icy server http://%s:%s%s" % (s.host, s.port, s.mount))
    s.open()
except shout.ShoutException as msg:
    print("Error connecting to icy server: %s" % str(msg))
    killbuffer('SHOUTERROR',None)
    fipbuffer.join()
    sys.exit(1)

try:
    while fipbuffer.getruntime() < opts.delay:
        _remains = (opts.delay - fipbuffer.getruntime())/60 or 1
        sys.stdout.write("\rBuffering for %0.0f min. " % _remains)
        sys.stdout.flush()
        time.sleep(10)
except KeyboardInterrupt:
    print("Killing %s" % fipbuffer.getName())
    killbuffer('KEYBOARDINTERRUPT', None)
    fipbuffer.join()
    sys.exit()

# s = shout.Shout()
# print("Using libshout version %s" % shout.version())
# 
# s.host = config['USEROPTS']['HOST']
# s.port = int(config['USEROPTS']['PORT'])
# s.user = config['USEROPTS']['USER']
# s.password = config['USEROPTS']['PASSWORD']
# s.mount = config['USEROPTS']['MOUNT']
# s.name = config['USEROPTS']['NAME']
# s.genre = config['USEROPTS']['GENRE']
# s.url = config['USEROPTS']['URL']
# s.public = int(config['USEROPTS']['PUBLIC'])
# s.format = 'mp3'
# s.protocol = 'http'
# s.audio_info = {shout.SHOUT_AI_SAMPLERATE: '48000',
#                 shout.SHOUT_AI_CHANNELS: '2',
#                 shout.SHOUT_AI_BITRATE: '128'}
# try:
#     print("Starting icy server http://%s:%s%s" % (s.host, s.port, s.mount))
#     s.open()
# except shout.ShoutException as msg:
#     print("Error connecting to icy server: %s" % str(msg))
#     killbuffer('SHOUTERROR',None)
#     sys.exit(1)

sys.stdout.write("\n\n\n")
while not fqueue.empty():
    try:
        _f = fqueue.get(timeout=10)
        fa = _f[1]
        _h, _m = timeinhours(time.time() - _f[0])
        _mb = (fqueue.qsize()*128)/1024
        sys.stdout.write("\033[F\033[F\033[2K\rOpening %s (%0.0fh:%0.0fm) %0.2f MB \n" % (
            fa, _h, _m, _mb))
        sys.stdout.write("\033[2K\rTrack: %s \n" % _f[2]['track'])
        sys.stdout.write("\033[2K\rArtist: %s " % _f[2]['artist'])
        sys.stdout.flush()
        with open(fa, 'rb') as fh:
            s.set_metadata({'song': _f[2]['track'],
                            'artist': _f[2]['artist']})  # only 'song' does anything
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
cleantmpdir(TMPDIR)
