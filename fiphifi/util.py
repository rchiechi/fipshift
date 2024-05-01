import os
import time
import json
import subprocess
import queue
import re

TSRE = re.compile(r'(.*?/fip_aac_hifi_\d_)(\d+)_(\d+)\.ts.*')

def parsets(ts):
    _m = re.match(TSRE, ts)
    try:
        tsid = [int(_m.group(2)), int(_m.group(3))]
    except (AttributeError, IndexError, ValueError):
        tsid = [0,0]
    return tsid

def get_tmpdir(_c):
    return os.path.join(_c['TMPDIR'], 'fipshift')

def cleantmpdir(tmpdir):
    n = 0
    for root, __, files in os.walk(tmpdir):
        for _f in files:
            _old = os.path.join(root, _f)
            if _f[-4:].lower() == ('.log'):
                if time.time() - os.stat(_old).st_ctime > 300:
                    _new = os.path.join(root, _f) + '.1'
                    if os.path.exists(_new):
                        os.remove(_new)
                    os.rename(_old, _new)
                    n += 1
            if _f[-6:].lower() == '.cache':
                if time.time() - os.stat(_old).st_mtime > 600:
                    os.remove(_old)
                    n += 1
            if _f[-3:].lower() == '.ts':
                if time.time() - os.stat(_old).st_mtime > 600:
                    os.remove(_old)
                    n += 1
    return n


def checkcache(cache):
    _urlqueue = queue.SimpleQueue()
    _urlz = []
    if os.path.exists(cache):
        with open(cache) as fh:
            try:
                _urlz = json.load(fh)
                for _url in _urlz:
                    _urlqueue.put_nowait(_url)
            except json.JSONDecodeError:
                os.remove(cache)
    return _urlz, _urlqueue

def writecache(cache, _urlz):
    with open(cache, 'w') as fh:
        json.dump(_urlz, fh)


def vampstream(FFMPEG, _c):
    _ffmpegcmd = [FFMPEG,
                  '-loglevel', 'fatal',
                  '-nostdin',
                  '-re',
                  '-i', 'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance',
                  '-content_type', 'audio/aac',
                  '-ice_name', 'FipShift',
                  '-ice_description', 'Time-shifted FIP stream',
                  '-ice_genre', 'Eclectic',
                  '-c:a', 'copy',
                  '-f', 'adts',
                  f"icecast://{_c['USER']}:{_c['PASSWORD']}@{_c['HOST']}:{_c['PORT']}/{_c['MOUNT']}"]
    return subprocess.Popen(_ffmpegcmd)

def delayedstream(_c, playlist):
    _ffmpegcmd = [_c['FFMPEG'],
                  '-loglevel', 'warning',
                  '-nostdin',
                  '-re',
                  '-stream_loop', '-1',
                  '-safe', '0',
                  '-i', playlist,
                  '-f', '-concat',
                  '-flush_packets', '0',
                  '-content_type', 'audio/aac',
                  '-ice_name', 'FipShift',
                  '-ice_description', 'Time-shifted FIP stream',
                  '-ice_genre', 'Eclectic',
                  '-c', 'copy',
                  '-f', 'adts',
                  f"icecast://{_c['USER']}:{_c['PASSWORD']}@{_c['HOST']}:{_c['PORT']}/{_c['MOUNT']}"]
    return subprocess.Popen(_ffmpegcmd,
                            stdin=subprocess.PIPE,
                            stdout=open(os.path.join(get_tmpdir(_c), 'ffmpeg.log'), 'w'),
                            stderr=subprocess.STDOUT)
