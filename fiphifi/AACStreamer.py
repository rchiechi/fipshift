import bitstring

class TSParser:
    # TS packet is 188 bytes
    TS_PACKET_SIZE = 188
    # AAC ADTS frame header is 7 bytes
    ADTS_HEADER_SIZE = 7

    def __init__(self):
        self.pid = None  # Program ID for AAC stream
        self.aac_data = bytearray()

    def parse_ts_file(self, data):
        """Parse TS file and extract AAC frames"""
        position = 0
        while position + self.TS_PACKET_SIZE <= len(data):
            packet = data[position:position + self.TS_PACKET_SIZE]
            self._parse_packet(packet)
            position += self.TS_PACKET_SIZE
        return self.aac_data

    def _parse_packet(self, packet):
        bits = bitstring.BitString(packet)
        
        # TS packet header
        sync_byte = bits.read('uint:8')
        if sync_byte != 0x47:  # TS sync byte
            return

        # Parse transport error, payload start, priority
        flags = bits.read('uint:3')
        payload_start = bool(flags & 0x4)
        
        # Get PID
        pid = bits.read('uint:13')
        if self.pid is None:
            # Look for audio stream PID in PMT
            if self._is_pmt_packet(bits):
                self.pid = self._find_audio_pid(bits)
            return

        if pid != self.pid:
            return

        # Parse adaptation field control
        adaptation = bits.read('uint:2')
        scrambling = bits.read('uint:2')
        
        if scrambling != 0:
            return

        # Skip adaptation field if present
        if adaptation & 0x2:
            adaptation_length = bits.read('uint:8')
            bits.pos += adaptation_length * 8

        # Extract PES packet
        if payload_start:
            self._parse_pes_packet(bits)
        else:
            # Continue previous PES packet
            remaining = bits.length - bits.pos
            self.aac_data.extend(bits.read(f'bytes:{remaining//8}'))

    def _parse_pes_packet(self, bits):
        # PES packet header
        if bits.read('bytes:3') != b'\x00\x00\x01':
            return

        stream_id = bits.read('uint:8')
        packet_length = bits.read('uint:16')
        
        # Optional PES header
        bits.pos += 2  # Skip flags
        header_length = bits.read('uint:8')
        bits.pos += header_length * 8

        # Extract AAC data
        remaining = bits.length - bits.pos
        self.aac_data.extend(bits.read(f'bytes:{remaining//8}'))

    def _is_pmt_packet(self, bits):
        """Check if packet contains Program Map Table"""
        table_id = bits.peek('uint:8')
        return table_id == 0x02

    def _find_audio_pid(self, bits):
        """Extract AAC stream PID from PMT"""
        # Skip to program info length
        bits.pos += 12
        program_info_length = bits.read('uint:12')
        bits.pos += program_info_length * 8

        while bits.pos < bits.length - 32:
            stream_type = bits.read('uint:8')
            if stream_type == 0x0F:  # AAC ADTS
                elem_pid = bits.read('uint:13')
                return elem_pid
            # Skip ES info
            bits.pos += 4  # Reserved bits
            es_info_length = bits.read('uint:12')
            bits.pos += es_info_length * 8
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