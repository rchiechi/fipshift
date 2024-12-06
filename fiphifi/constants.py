import re

FIPBASEURL = 'https://stream.radiofrance.fr'
FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
VAMPURL = 'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance'
#METAURL = 'https://www.radiofrance.fr/fip/api/live/webradios/fip'
METAURL = 'https://www.radiofrance.fr/fip/api/live?'
AACRE = re.compile(fr'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
STRPTIME = "%Y-%m-%dT%H:%M:%SZ"
BUFFERSIZE = 5
TSLENGTH = 4

METATEMPLATE = {
    "stationName": "fip",
    "delayToRefresh": 10000,
    "migrated": True,
    "now": {
        "printProgMusic": False,
        "startTime": 1711410121,
        "endTime": 1711410413,
        "producer": "",
        "firstLine": {
            "title": "Digital love",
            "id": None,
            "path": None
        },
        "secondLine": {
            "title": "Daft Punk",
            "id": None,
            "path": None
        },
        "thirdLine": {
            "title": None,
            "id": None,
            "path": None
        },
        "song": {
            "id": "e35b8e81-d404-4518-94ae-31823b11a748",
            "year": 2001,
            "release": {
                "label": None,
                "title": "Discovery",
                "reference": None
            }
        },
        "media": {
            "startTime": 1711410121,
            "endTime": 1711410413,
            "sources": [
                {
                    "url": "https://stream.radiofrance.fr/fip/fip.m3u8?id=radiofrance",
                    "broadcastType": "live",
                    "format": "hls",
                    "bitrate": 0
                },
                {
                    "url": "https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance",
                    "broadcastType": "live",
                    "format": "aac",
                    "bitrate": 192
                },
                {
                    "url": "https://icecast.radiofrance.fr/fip-midfi.aac?id=radiofrance",
                    "broadcastType": "live",
                    "format": "aac",
                    "bitrate": 128
                },
                {
                    "url": "https://icecast.radiofrance.fr/fip-midfi.mp3?id=radiofrance",
                    "broadcastType": "live",
                    "format": "mp3",
                    "bitrate": 128
                },
                {
                    "url": "https://icecast.radiofrance.fr/fip-lofi.aac?id=radiofrance",
                    "broadcastType": "live",
                    "format": "aac",
                    "bitrate": 32
                },
                {
                    "url": "https://icecast.radiofrance.fr/fip-lofi.mp3?id=radiofrance",
                    "broadcastType": "live",
                    "format": "mp3",
                    "bitrate": 32
                }
            ]
        },
        "localRadios": [],
        "visuals": {
            "card": {
                "model": "EmbedImage",
                "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/10/469bac58-6c12-4ac7-b97c-dabea8eeac70/200x200_rf_omm_0000081008_dnc.0057667459.jpg",
                "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/10/469bac58-6c12-4ac7-b97c-dabea8eeac70/200x200_rf_omm_0000081008_dnc.0057667459.webp",
                "legend": None,
                "copyright": None,
                "author": None,
                "width": 200,
                "height": 200,
                "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAAEEAgMF/8QAIhAAAgEEAQUBAQAAAAAAAAAAAQIAAwQREiETIjEyQVFh/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAH/xAAVEQEBAAAAAAAAAAAAAAAAAAAAAf/aAAwDAQACEQMRAD8A8eEaqWOAMmUpauF3bhYEsJQLV9hxgGdOjSJwcqq+xgRwm6oQN2Ekf2YgU2lKpUctTIGvJlLtURRgh18ye1r9BHK+x4Ea3jYwQPOTA6vUrGlroQfE1b2z1AQ/CoOR+mcjeMdQB9yYq92/aqNjHJI+xBPVVFYgHM5zbsGO30zMoIQhIAEiKOKARxRwP//Z",
                "id": "469bac58-6c12-4ac7-b97c-dabea8eeac70",
                "type": "image",
                "preset": "200x200"
            },
            "player": {
                "model": "EmbedImage",
                "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/10/469bac58-6c12-4ac7-b97c-dabea8eeac70/200x200_rf_omm_0000081008_dnc.0057667459.jpg",
                "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/10/469bac58-6c12-4ac7-b97c-dabea8eeac70/200x200_rf_omm_0000081008_dnc.0057667459.webp",
                "legend": None,
                "copyright": None,
                "author": None,
                "width": 200,
                "height": 200,
                "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAAEEAgMF/8QAIhAAAgEEAQUBAQAAAAAAAAAAAQIAAwQREiETIjEyQVFh/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAH/xAAVEQEBAAAAAAAAAAAAAAAAAAAAAf/aAAwDAQACEQMRAD8A8eEaqWOAMmUpauF3bhYEsJQLV9hxgGdOjSJwcqq+xgRwm6oQN2Ekf2YgU2lKpUctTIGvJlLtURRgh18ye1r9BHK+x4Ea3jYwQPOTA6vUrGlroQfE1b2z1AQ/CoOR+mcjeMdQB9yYq92/aqNjHJI+xBPVVFYgHM5zbsGO30zMoIQhIAEiKOKARxRwP//Z",
                "id": "469bac58-6c12-4ac7-b97c-dabea8eeac70",
                "type": "image",
                "preset": "200x200"
            }
        }
    },
    "next": {
        "printProgMusic": False,
        "startTime": 0,
        "endTime": 0,
        "producer": "",
        "firstLine": {
            "title": "Le direct",
            "id": None,
            "path": None
        },
        "secondLine": {
            "title": "La radio la plus \u00e9clectique du monde",
            "id": None,
            "path": None
        },
        "thirdLine": {
            "title": None,
            "id": None,
            "path": None
        },
        "song": None
    }
}
