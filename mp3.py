import struct
import sys
import logging
# MP3 frames are not independent because of the byte reservoir. This script does not account for
# that in determining where to do the split.
# https://stackoverflow.com/questions/2952309/python-library-to-split-and-join-mp3-files

logger = logging.getLogger(__name__)

def detectlastframe(fi):

    #Constants for MP3
    bitrates = {0x0: "free", 0x1: 32, 0x2: 40, 0x3: 48, 0x4: 56, 0x5: 64, 0x6: 80, 0x7: 96, 0x8: 112,
        0x9: 128, 0xa: 160, 0xb: 192, 0xc: 224, 0xd: 256, 0xe: 320, 0xf: "bad"}
    freqrates = {0x0: 44100, 0x1: 48000, 0x2: 32000, 0x3: "reserved"}
    countMpegFrames = 0
    frameDuration = 0.026
    unrecognizedBytes = 0
    reservedbits = 0
    fi.seek(0)
    framepos = fi.tell()
    
    while True:
    
        startPos = fi.tell()
    
        #Check for 3 byte headers
        id3Start = fi.read(3)
        if len(id3Start) == 3:
    
            if id3Start == b'TAG':
                logger.debug("Found ID3 v1/1.1 header")
                fi.seek(startPos + 256)
                continue
    
            if id3Start == b'ID3':
                #Possibly a ID3v2 header
                majorVer, minorVer, flags, encSize = struct.unpack(">BBBI", fi.read(7))
                if majorVer != 0xFF and minorVer != 0xFF:
                    encSize1 = (encSize & 0x7f000000) >> 24
                    encSize2 = (encSize & 0x7f0000) >> 16
                    encSize3 = (encSize & 0x7f00) >> 8
                    encSize4 = (encSize & 0x7f)
                    if encSize1 < 0x80 and encSize2 < 0x80 and encSize3 < 0x80 and encSize4 < 0x80:
                        size = ((encSize & 0x7f000000) >> 3) + ((encSize & 0x7f0000) >> 2) + ((encSize & 0x7f00) >> 1) + (encSize & 0x7f)
                        unsync = (flags >> 7) & 0x1
                        extendedHeader = (flags >> 6) & 0x1
                        experimental = (flags >> 5) & 0x1
                        logger.debug("Found ID3v2 header")
                        logger.debug("version %s %s %s %s %s", majorVer, minorVer, unsync, extendedHeader, experimental)
                        logger.debug("size %s", size)
                        #TODO extendedHeader not supported
                        fi.seek(startPos + 10 + size)
                        continue
    
        #Check for 4 byte headers
        fi.seek(startPos)
        headerRaw = fi.read(4)
        if len(headerRaw) == 4:
            headerWord = struct.unpack(">I", headerRaw)[0]
            #Check for MPEG-1 audio frame
            if headerWord & 0xfff00000 == 0xfff00000:
                # logger.debug("Possible MPEG-1 audio header %s", hex(headerWord))
                countMpegFrames += 1
                ver = (headerWord & 0xf0000) >> 16
                bitrateEnc = (headerWord & 0xf000) >> 12
                freqEnc = (headerWord & 0xf00) >> 8
                mode = (headerWord & 0xf0) >> 4
                cpy = (headerWord & 0xf)
                if ver & 0xe == 0xa and freqEnc != 0xf:
                    framepos = fi.tell()-4
                    # logger.debug("Probably an MP3 frame at %s", framepos)
                    bitrate = bitrates[bitrateEnc]
                    freq = freqrates[freqEnc >> 2]
                    padding = ((freqEnc >> 1) & 0x1) == 1
                    # logger.debug("bitrate %s kbps", bitrate)
                    # logger.debug("freq %s Hz", freq)
                    # logger.debug("padding %s", padding)
                    try:
                        frameLen = int((144 * bitrate * 1000 / freq ) + padding)
                    except TypeError:
                        # logger.debug('Hit reserved bit.')
                        reservedbits += 1
                    continue
                # else:
                #     logger.debug("Unsupported format: %s header: %s", hex(ver), hex(headerWord))
    
        #If no header can be detected, move on to the next byte
        fi.seek(startPos)
        nextByteRaw = fi.read(1)
        if len(nextByteRaw) == 0:
            break #End of file
        unrecognizedBytes += 1
    logger.info("Probably an MP3 frame at %s", framepos)
    logger.debug("unrecognizedBytes: %s reserved bits: %s", unrecognizedBytes, reservedbits)
    return framepos
    


