import sys
import os
import logging

logger = logging.getLogger(__package__)


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


def getplayed(tmpfile):
    _played = []
    if not os.path.exists(tmpfile):
        logger.warning("%s does not exist, cannot parse log.", tmpfile)
        return _played
    with open(tmpfile, 'rb') as fh:
        if os.path.getsize(tmpfile) >= 524288:
            fh.seek(-524288, 2)
        for _l in fh:
            # [2021-09-20  13:44:15] INFO playlist-builtin/playlist_read Currently playing "/tmp/fipshift/ices/0000000000000021"
            if b'Currently playing' in _l:
                _played.append(_l.split(b'"')[-2])
    if not _played:
        logger.warning('Did not find any entries in %s', tmpfile)
    return _played


def getplaylist(playlist):
    _playlist = []
    if not os.path.exists(playlist):
        logger.warning("%s does not exist, cannot parse playlist.", playlist)
        return _playlist
    with open(playlist, 'rb') as fh:
        for _l in fh:
            _playlist.append(_l.strip())
    if not _playlist:
        logger.warning('Did not find any entries in %s', playlist)
    return _playlist


def timeinhours(sec):
    sec_value = sec % (24 * 3600)
    hour_value = sec_value // 3600
    sec_value %= 3600
    mins = sec_value // 60
    sec_value %= 60
    return hour_value, mins

class RestartTimeout(Exception):
    def __init__(self, expression, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(expression)
        # Now for your custom code...
        self.errors = message