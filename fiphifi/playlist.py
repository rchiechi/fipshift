import time
import logging
import threading
import json
import datetime as dt
from fiphifi.util import parsets, checkcache
from fiphifi.constants import FIPBASEURL, FIPLIST, STRPTIME, BUFFERSIZE, TSLENGTH
from fiphifi.M3U8Handler import M3U8Handler
import requests

logger = logging.getLogger(__package__ + '.playlist')

class FipPlaylist(threading.Thread):
    offset = -4
    delay = 5
    duration = TSLENGTH

    def __init__(self, _alive, dlqueue, cache_file):
        threading.Thread.__init__(self)
        self.name = 'FipPlaylist Thread'
        self._alive = _alive
        self.cache_file = cache_file
        self.dlqueue = dlqueue  # Save reference to dlqueue
        self._history, self.buff = checkcache(self.cache_file)
        self.lock = threading.Lock()
        self.last_update = time.time()
        
        # Populate dlqueue with cached items
        for url_data in self._history:
            self.dlqueue.put(url_data)
            
        self.m3u8_handler = M3U8Handler(FIPBASEURL, self.dlqueue)  # Use dlqueue for new segments
        for url_data in self._history:
            self.m3u8_handler.ingest_url(url_data)

    def run(self):
        logger.info('Starting %s', self.name)
        if not self.alive:
            logger.warn("%s called without alive set.", self.name)
            
        self.checkhistory()
        retries = 0
        fip_error = False
        
        # Calculate timezone offset
        self.offset = time.gmtime().tm_hour - dt.datetime.now().hour
        logger.info(f'Using offset of -{self.offset} hours in playlist')
        
        while self.alive:
            try:
                req = requests.get(FIPLIST, timeout=self.delay)
                if req.ok:
                    # Use M3U8Handler to parse playlist
                    if self.m3u8_handler.parse_playlist(req.text):
                        retries = 0
                        self.last_update = time.time()
                        # Sync our history with handler's history
                        self._history = self.m3u8_handler.history
                        # Write to cache periodically
                        self.writecache()
                        # Prune old segments
                        self.m3u8_handler.prune_history(self.buff.qsize() + BUFFERSIZE)
                    else:
                        logger.warning("Failed to parse playlist")
                        
            except requests.exceptions.ConnectionError as error:
                fip_error = True
                logger.warning("%s: A ConnectionError has occurred: %s", self.name, error)
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
                fip_error = True
                logger.warning("%s request timed out", self.name)
            finally:
                if fip_error:
                    retries += 1
                    fip_error = False
                    if retries > 9:
                        logger.error("%s Maximum retries reached, dying.", self.name)
                        self._alive.clear()
                    else:
                        logger.warning("%s error, retrying (%s)", self.name, retries)
                        continue
                time.sleep(self.delay)
                
        logger.info('%s wrote %s urls to cache', self.name, self.writecache())
        logger.warning('%s ended (alive: %s)', self.name, self.alive)

    def writecache(self):
        with self.lock:
            with open(self.cache_file, 'w') as fh:
                json.dump(self._history, fh)
        logger.info("%s cache: %0.0f min", self.name, len(self._history) * TSLENGTH / 60)
        return len(self._history)

    def checkhistory(self):
        """Initialize sequence tracking from cached history"""
        logger.info('Loaded %s entries from cache.', self.qsize)
        # Let M3U8Handler process the history
        with self.lock:
            for url_data in self._history:
                self.m3u8_handler.ingest_url(url_data)

    # Keep existing property methods
    @property
    def alive(self):
        return self._alive.isSet()

    @property
    def lastupdate(self):
        return time.time() - self.last_update

    @property
    def history(self):
        return self._history[:]  # Return a copy of the history list

    @property
    def urlq(self):
        return self.buff

    @urlq.setter
    def urlq(self, _queue):
        self.buff = _queue
        # Update M3U8Handler's queue reference
        self.m3u8_handler.urlq = _queue

    @property
    def qsize(self):
        if self.buff.empty():
            return 0
        return self.buff.qsize()

    @property
    def tslength(self):
        return self.duration