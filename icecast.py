import os
import urllib.request
import json
import threading
import logging
import time
from urllib.error import HTTPError, URLError
from socket import timeout as socket_timeout


# Send

# SOURCE /mp3test ICE/1.0
# content-type: audio/mpeg
# Authorization: Basic c291cmNlOmhhY2ttZQ==
# ice-name: This is my server name
# ice-url: http://www.google.com
# ice-genre: Rock
# ice-bitrate: 128
# ice-private: 0
# ice-public: 1
# ice-description: This is my server description
# ice-audio-info: ice-samplerate=44100;ice-bitrate=128;ice-channels=2

# Metadata channel

# GET /admin/metadata?pass=hackme&mode=updinfo&mount=/mp3test&song=Even%20more%20meta%21%21 HTTP/1.0
# Authorization: Basic c291cmNlOmhhY2ttZQ==
# User-Agent: (Mozilla Compatible)

# Response

# HTTP/1.0 200 OK
# Content-Type: text/xml
# Content-Length: 113
# 
# <?xml version="1.0"?>
# <iceresponse><message>Metadata update successful</message><return>1</return></iceresponse>

# https://gist.github.com/niko/2a1d7b2d109ebe7f7ca2f860c3505ef0

#  https://stream.radiofrance.fr/fip/fip_hifi.m3u8\?id\=radiofrance

class Ices(threading.Thread):
    
    def __init__(self, _username, _password, _iceserver, _mount):
        threading.Thread.__init__(self)