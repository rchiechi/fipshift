import os
import time
import json
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
                os.replace(_old, f'{_old}.1')
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

