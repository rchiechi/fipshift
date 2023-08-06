import os
import time
import json
import queue
# import sys
# import subprocess
# from fiphifi.metadata import send_metadata  # type: ignore
# import logging
# import threading

# logger = logging.getLogger(__package__)

# def waitdelay(logger, epoch, delay, config, FFMPEG):
#     logger.info('Starting vamp stream.')

#     _c = config['USEROPTS']
#     _ffmpegcmd = [FFMPEG,
#                   '-loglevel', 'fatal',
#                   '-re',
#                   '-i', 'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance',
#                   '-content_type', 'audio/aac',
#                   '-ice_name', 'FipShift',
#                   '-ice_description', 'Time-shifted FIP stream',
#                   '-ice_genre', 'Eclectic',
#                   '-c:a', 'copy',
#                   '-f', 'adts',
#                   f"icecast://{_c['USER']}:{_c['PASSWORD']}@{_c['HOST']}:{_c['PORT']}/{_c['MOUNT']}"]
#     ffmpeg_proc = subprocess.Popen(_ffmpegcmd)

#     try:
#         _runtime = time.time() - epoch
#         while _runtime < delay:
#             _remains = (delay - _runtime) / 60 or 1
#             logger.info('Buffering for %0.0f more minutes', _remains)
#             time.sleep(60)
#             if ffmpeg_proc.poll() is not None:
#                 logger.warning('Restarting vamp stream.')
#                 ffmpeg_proc = subprocess.Popen(_ffmpegcmd)
#             send_metadata(f"{_c['HOST']}:{_c['PORT']}",
#                           _c['MOUNT'],
#                           f"Realtime Stream: T-{_remains:0.0f} minutes",
#                           (config['USEROPTS']['USER'], config['USEROPTS']['PASSWORD']))
#             _runtime = time.time() - epoch

#     except KeyboardInterrupt:
#         logger.info("Killing threads")
#         ffmpeg_proc.terminate()
#         ALIVE.clear()
#         for child in children:
#             if children[child].is_alive():
#                 logger.info("Joining %s", children[child].name)
#                 children[child].join(timeout=30)
#         cleantmpdir(TMPDIR)
#         sys.exit()


def cleantmpdir(tmpdir):
    n = 0
    for root, __, files in os.walk(tmpdir):
        for _f in files:
            _old = os.path.join(root, _f)
            if _f[-4:].lower() == ('.log'):
                if time.time() - os.stat(_old).st_ctime > 120:
                    _new = os.path.join(root, _f) + '.1'
                    if os.path.exists(_new):
                        os.remove(_new)
                    os.rename(_old, _new)
                    n += 1
            if _f[-6:].lower() == '.cache':
                if time.time() - os.stat(_old).st_mtime > 120:
                    os.remove(_old)
                    n += 1
    return n


def checkcache(cache, pl_queue):
    if not os.path.exists(cache):
        return
    with open(cache) as fh:
        try:
            _urlz = json.load(fh)
            for _url in _urlz:
                pl_queue.put(_url)
        except json.JSONDecodeError:
            os.remove(cache)
            pass


def writecache(cache, _urlz):
    if os.path.exists(cache):
        os.remove(cache)
    with open(cache, 'w') as fh:
        json.dump(_urlz, fh)
