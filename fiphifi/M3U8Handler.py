import re
import time
import logging
import queue
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from urllib.parse import urljoin

logger = logging.getLogger(__package__ + '.m3u8handler')

class M3U8Handler:
    """Handles FIP HLS playlist parsing and segment tracking"""
    
    def __init__(self, base_url: str, urlq: queue.SimpleQueue):
        self.base_url = base_url
        self.urlq = urlq
        self.duration = 4.0  # Standard segment duration
        self.last_update = time.time()
        self._history = []
        self.offset = self._calculate_offset()
        
        # Keep track of segments for continuity checking
        self.idx = {0: 0}  # Maps prefix to list of suffixes
        
        # Compile regex patterns
        self.ts_pattern = re.compile(r'(.*?/fip_aac_hifi_\d_)(\d+)_(\d+)\.ts.*')
        self.date_pattern = re.compile(r'#EXT-X-PROGRAM-DATE-TIME:(.+)Z')
        self.sequence_pattern = re.compile(r'#EXT-X-MEDIA-SEQUENCE:(\d+)')
        
        logger.info(f'Using offset of -{self.offset} hours in playlist handler')
        
    def _calculate_offset(self):
        """Calculate timezone offset from GMT"""
        now = datetime.now(timezone.utc)
        local = datetime.now()
        return round((now.replace(tzinfo=None) - local).total_seconds() / 3600)
        
    def parse_playlist(self, content: str) -> bool:
        """Parse M3U8 content and queue new segments"""
        lines = content.splitlines()
        if not lines:
            logger.warning("Empty playlist")
            return False
            
        current_timestamp = None
        success = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Parse program date
            if m := self.date_pattern.match(line):
                try:
                    # Parse the UTC time properly
                    utc_dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    # Convert to local time
                    local_dt = utc_dt.astimezone()
                    current_timestamp = local_dt.timestamp()
                    logger.debug(f"Converted UTC {utc_dt} to local timestamp {current_timestamp}")
                except ValueError as e:
                    logger.warning(f"Failed to parse timestamp: {e}")
                continue
                
            # Parse segment URL
            if not line.startswith('#'):
                url = urljoin(self.base_url, line)
                if current_timestamp:
                    success = self.ingest_url([current_timestamp, url])
                    
        self.last_update = time.time()
        return success
        
    def ingest_url(self, url_data: Tuple[float, str]) -> bool:
        """Process and queue a new segment if valid"""
        timestamp, url = url_data
        
        # Parse TS filename components
        match = self.ts_pattern.match(url)
        if not match:
            logger.warning(f'Malformed url: {url}')
            return False
            
        prefix = int(match.group(2))  # stream identifier
        suffix = int(match.group(3))  # sequence number
        
        # Check if we've seen this URL before
        if url_data in self._history:
            logger.debug(f"M3U overlap {prefix}:{suffix}")
            return False
            
        # Validate sequence continuity
        if prefix in self.idx:
            last_suffix = self.idx[prefix][-1] if isinstance(self.idx[prefix], list) else self.idx[prefix]
            
            if suffix > last_suffix:
                if isinstance(self.idx[prefix], list):
                    self.idx[prefix].append(suffix)
                else:
                    self.idx[prefix] = [self.idx[prefix], suffix]
                    
                if suffix - last_suffix > 1:
                    logger.warning(f"Skipped a file {prefix}: {last_suffix} -> {suffix}")
                    
            elif suffix < last_suffix:
                logger.debug(f"Backwards url order {prefix}: {last_suffix} -> {suffix}")
                return False
                
            elif suffix == last_suffix:
                logger.debug(f"Same url twice in a row {prefix}: {suffix}")
                return False
                
        else:
            logger.debug(f"Incrementing prefix: {prefix}")
            self.idx = {prefix: [suffix]}
            
        # Store and queue the URL
        self._history.append(url_data)
        try:
            self.urlq.put(url)
            logger.debug(f"Successfully queued URL {url} with timestamp {timestamp}")
        except Exception as e:
            logger.error(f"Failed to queue URL {url}: {e}")
            return False
            
        logger.debug(f"Cached local timestamp {timestamp} ({datetime.fromtimestamp(timestamp)}) @ {prefix}:{suffix}")
        return True
        
    def prune_history(self, max_segments: int):
        """Remove old segments from history"""
        if len(self._history) > max_segments:
            self._history = self._history[-max_segments:]
            
    @property
    def history(self):
        return self._history[:]
        
    @property
    def qsize(self):
        return self.urlq.qsize()