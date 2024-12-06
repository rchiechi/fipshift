import os
import time
import logging
import threading
import queue
import re
from typing import Optional, Tuple
from urllib.parse import urlparse
from fiphifi.util import parsets, get_tmpdir
from fiphifi.icecast import IcecastClient
from fiphifi.AACStreamer import AACStreamer
from fiphifi.constants import AACRE

logger = logging.getLogger(__package__+'.buffer')

class Buffer(threading.Thread):
    duration = 4  # TSLENGTH
    
    def __init__(self, _alive, urlq, config):
        threading.Thread.__init__(self)
        self.name = 'Buffer Thread'
        self._alive = _alive
        self.urlq = urlq
        self.dldir = os.path.join(get_tmpdir(config['USEROPTS']), 'ts')
        self._timestamp = [[0, time.time()]]
        self.last_timestamp = 0
        self.sent_files = set()
        
        # Ensure download directory exists
        os.makedirs(self.dldir, exist_ok=True)
        
        # Initialize Icecast client
        self.icecast = IcecastClient(
            host=config['USEROPTS']['HOST'],
            port=int(config['USEROPTS']['PORT']),
            mount=config['USEROPTS']['MOUNT'],
            username=config['USEROPTS']['USER'],
            password=config['USEROPTS']['PASSWORD']
        )
        self.aacstreamer = AACStreamer(self.icecast)
        # Start the connection
        if not self.icecast.start():
            raise ConnectionError("Failed to initialize Icecast connection")
            
    def get_ts_filename(self, url: str) -> str:
        """Extract the .ts filename from URL and ensure it's valid"""
        match = AACRE.match(url)
        if match:
            filename = match.group(1)
            return os.path.join(self.dldir, filename)
        else:
            # Fallback to simpler parsing if regex fails
            parsed = urlparse(url)
            path = parsed.path
            if path.endswith('.ts'):
                filename = os.path.basename(path).split('?')[0]
                return os.path.join(self.dldir, filename)
        raise ValueError(f"Invalid TS URL format: {url}")

    def run(self):
        logger.info('Starting Buffer')
        try:
            while self.alive and self.icecast.is_connected:
                if not self.process_next_segment():
                    time.sleep(0.5)
                self.cleanup_sent_files()
                    
        except Exception as msg:
            logger.error("%s died %s", self.name, str(msg))
        finally:
            self.cleanup()
            logger.warning('%s ending.', self.name)

    def process_next_segment(self) -> bool:
        """Process the next segment from the queue"""
        try:
            # Get next segment from queue
            _timestamp, _url = self.urlq.get(timeout=self.duration)
            
            try:
                _ts = self.get_ts_filename(_url)
            except ValueError as e:
                logger.error(str(e))
                return False
                
            # Verify file exists and is readable
            if not os.path.isfile(_ts):
                logger.warning(f"File not found: {_ts}")
                return False
                
            try:
                if os.path.getsize(_ts) < 4096:
                    logger.warning(f"File too small: {_ts}")
                    return False
            except OSError as e:
                logger.error(f"Error checking file {_ts}: {e}")
                return False
                
            # Read and send the file
            try:
                if self.aacstreamer.stream_file(_ts):
                    # Only add to sent_files if successfully sent
                    self.sent_files.add(_ts)
                    parsed = parsets(_ts)
                    if parsed[1] != 0:  # Only add valid timestamps
                        self._timestamp.append([parsed[1], _timestamp])
                    logger.debug(f"Successfully sent {os.path.basename(_ts)}")
                    return True
            except IOError as e:
                logger.error(f"Error reading file {_ts}: {e}")
                return False
                    
            return False
            
        except queue.Empty:
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing segment: {e}")
            return False
            
    def cleanup_sent_files(self):
        """Delete files that have been successfully sent"""
        current_time = time.time()
        files_to_remove = set()
        
        for ts_file in list(self.sent_files):  # Create copy for iteration
            if not os.path.exists(ts_file):
                files_to_remove.add(ts_file)
                continue
                
            try:
                if current_time - os.path.getmtime(ts_file) > self.duration * 2:
                    try:
                        os.remove(ts_file)
                        logger.debug(f"Removed sent file: {os.path.basename(ts_file)}")
                    except OSError as e:
                        logger.warning(f"Failed to remove {ts_file}: {e}")
                    files_to_remove.add(ts_file)
            except OSError as e:
                logger.warning(f"Error checking file {ts_file}: {e}")
                files_to_remove.add(ts_file)
                
        # Remove processed files from tracking set
        self.sent_files -= files_to_remove
            
    def cleanup(self):
        """Clean up resources when stopping"""
        logger.info("Cleaning up buffer resources")
        
        # Stop Icecast client
        if self.icecast:
            self.icecast.stop()
            
        # Final cleanup of any remaining files
        for ts_file in list(self.sent_files):  # Create copy for iteration
            try:
                if os.path.exists(ts_file):
                    os.remove(ts_file)
                    logger.debug(f"Cleaned up file: {os.path.basename(ts_file)}")
            except OSError as e:
                logger.warning(f"Failed to clean up {ts_file}: {e}")
                
        self.sent_files.clear()

    @property
    def timestamp(self):
        """Get timestamp for current segment"""
        _timestamp = self.last_timestamp
        for _i, _item in enumerate(self._timestamp):
            if _item[0] == self.current_segment:
                _timestamp = _item[1]
                self.last_timestamp = _timestamp
                self._timestamp = self._timestamp[_i:]
                break
        return _timestamp
        
    @property
    def current_segment(self):
        """Get currently playing segment number"""
        if self._timestamp:
            return self._timestamp[-1][0]
        return 0
        
    @property
    def alive(self):
        return self._alive.isSet()
        
    @property
    def initialized(self):
        return self.icecast.is_connected
        
    @property
    def tslength(self):
        return self.duration
        
    @tslength.setter 
    def tslength(self, _duration):
        if _duration > 0:
            self.duration = _duration
        else:
            logger.error("%s not setting tslength < 0", self.name)