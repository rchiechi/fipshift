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