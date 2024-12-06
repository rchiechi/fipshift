import struct

class TSParser:
    TS_PACKET_SIZE = 188
    ADTS_HEADER_SIZE = 7

    def __init__(self):
        self.pid = None
        self.aac_data = bytearray()

    def parse_ts_file(self, data):
        for i in range(0, len(data), self.TS_PACKET_SIZE):
            packet = data[i:i + self.TS_PACKET_SIZE]
            if len(packet) == self.TS_PACKET_SIZE:
                self._parse_packet(packet)
        return self.aac_data

    def _parse_packet(self, packet):
        # Check sync byte
        if packet[0] != 0x47:
            return

        # Parse PID (13 bits from bytes 1-2)
        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        
        if self.pid is None:
            if self._is_pmt_packet(packet):
                self.pid = self._find_audio_pid(packet)
            return

        if pid != self.pid:
            return

        # Get adaptation field control
        adaptation = (packet[3] & 0x30) >> 4
        
        # Calculate payload start
        payload_start = 4
        if adaptation & 0x2:  # Has adaptation field
            adaptation_length = packet[4]
            payload_start += adaptation_length + 1

        # Extract payload
        self.aac_data.extend(packet[payload_start:])

    def _is_pmt_packet(self, packet):
        if len(packet) < 5:
            return False
        return packet[4] == 0x02

    def _find_audio_pid(self, packet):
        pos = 5
        while pos < len(packet) - 5:
            if packet[pos] == 0x0F:  # AAC ADTS
                pid = ((packet[pos + 1] & 0x1F) << 8) | packet[pos + 2]
                return pid
            pos += 5
        return None

class AACStreamer:
    def __init__(self, icecast_client):
        self.icecast = icecast_client
        self.parser = TSParser()
        
    def stream_file(self, ts_file):
        with open(ts_file, 'rb') as f:
            ts_data = f.read()
            
        aac_data = self.parser.parse_ts_file(ts_data)
        
        # Stream AAC frames
        pos = 0
        while pos < len(aac_data):
            # Find ADTS sync word (0xFFF)
            while pos < len(aac_data) - 1:
                if aac_data[pos:pos+2] == b'\xff\xf0':
                    break
                pos += 1
                
            if pos >= len(aac_data) - 1:
                break
                
            # Parse ADTS header
            header = aac_data[pos:pos + TSParser.ADTS_HEADER_SIZE]
            frame_length = ((header[3] & 0x03) << 11) | (header[4] << 3) | (header[5] >> 5)
            
            # Calculate and apply frame timing
            samples_per_frame = 1024  # AAC constant
            sample_rate = 48000  # From FIP stream
            frame_duration = samples_per_frame / sample_rate
            self.icecast.duration = frame_duration
            
            # Extract and send frame
            frame = aac_data[pos:pos + frame_length]
            self.icecast.send_data(frame)
            

            time.sleep(frame_duration)
            
            pos += frame_length