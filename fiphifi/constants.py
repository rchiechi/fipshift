import re

FIPBASEURL = 'https://stream.radiofrance.fr'
FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
# METAURL = 'https://www.radiofrance.fr/api/v2.1/stations/fip/live'
# METAURL = 'https://www.radiofrance.fr/api/v2.1/stations/fip/live/webradios/fip'
METAURL = 'https://www.radiofrance.fr/fip/api/live/webradios/fip'
AACRE = re.compile(f'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
TSRE= re.compile('(.*/fip_aac_hifi_\d_)(\d+)_(\d+)')
STRPTIME = "%Y-%m-%dT%H:%M:%SZ"

METATEMPLATE = {
              "delayToRefresh": 10000,
              "now": {
                            "firstLine": "Le Song",
                            "secondLine": "Le Artist",
                            "thirdLine": None,
                            "startTime": 1695290908,
                            "endTime": 1695291101,
                            "cardVisual": {
                                          "model": "EmbedImage",
                                          "author": None,
                                          "copyright": None,
                                          "height": 250,
                                          "id": "397f0712-12ca-4ca6-9f28-54ba89e723d0",
                                          "legend": None,
                                          "preset": "250x250",
                                          "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAFwABAQEBAAAAAAAAAAAAAAAAAwIBAP/EABcQAQEBAQAAAAAAAAAAAAAAAAEAEQL/xAAWAQEBAQAAAAAAAAAAAAAAAAAAAQP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwAQqC4Kws2jMsSTLEoBSnJUpyKQKgsKwg0LkqC3IBSnJUpyqJ5l5h5m4gQLktLWAuqJOo4P/9k=",
                                          "src": "https://www.radiofrance.fr/s3/cruiser-production/2021/08/397f0712-12ca-4ca6-9f28-54ba89e723d0/250x250_rf_omm_0002108015_dnc.0121591951.jpg",
                                          "type": "image",
                                          "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2021/08/397f0712-12ca-4ca6-9f28-54ba89e723d0/250x250_rf_omm_0002108015_dnc.0121591951.webp",
                                          "width": 250
                            },
                            "song": {
                                          "id": "4022bb60-3c72-4675-9968-5327b5e38740",
                                          "year": 1997,
                                          "release": {
                                                        "title": "Le Album",
                                                        "label": "Le Label"
                                          }
                            }
              },
              "migrated": True,
              "next": [{
                            "firstLine": "Le Song",
                            "secondLine": "Le Artist",
                            "thirdLine": None,
                            "startTime": 1695291101,
                            "endTime": 1695291229,
                            "cardVisual": {
                                          "model": "EmbedImage",
                                          "author": None,
                                          "copyright": None,
                                          "height": 250,
                                          "id": "8b5b2ef9-852a-444d-bc86-e49eefabb8b5",
                                          "legend": None,
                                          "preset": "250x250",
                                          "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGAABAQEBAQAAAAAAAAAAAAAAAQIDAAX/xAAYEAEBAQEBAAAAAAAAAAAAAAAAEQESAv/EABYBAQEBAAAAAAAAAAAAAAAAAAABAv/EABURAQEAAAAAAAAAAAAAAAAAAAAR/9oADAMBAAIRAxEAPwDzoI0gjTNTDFQ5gVEPK4YqVJTmqzQMMFNBzhuiiMc1eemWKxltr0OkOVFb6FToB//Z",
                                          "src": "https://www.radiofrance.fr/s3/cruiser-production/2023/07/8b5b2ef9-852a-444d-bc86-e49eefabb8b5/250x250_sc_rf_omm_0003521061_dnc.0137467698.jpg",
                                          "type": "image",
                                          "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2023/07/8b5b2ef9-852a-444d-bc86-e49eefabb8b5/250x250_sc_rf_omm_0003521061_dnc.0137467698.webp",
                                          "width": 250
                            },
                            "song": {
                                          "id": "946d8322-8e92-4f39-baec-3103904a73a7",
                                          "year": 1997,
                                          "release": {
                                                        "title": "Le Album",
                                                        "label": "Le Label"
                                          }
                            }
              }]
}

# METATEMPLATE = {"delayToRefresh": 10000,
#                 "now": {
#                   "firstLine": {
#                     "id": None,
#                     "title": "Le direct",
#                     "path": None
#                   },
#                   "secondLine": {
#                     "id": None,
#                     "title": "La radio la plus éclectique du monde",
#                     "path": None
#                   },
#                   "thirdLine": {
#                     "id": None,
#                     "title": None,
#                     "path": None
#                   },
#                   "printProgMusic": False,
#                   "startTime": None,
#                   "visuals": {
#                     "card": {
#                       "model": "EmbedImage",
#                       "author": None,
#                       "copyright": "Aucun(e)",
#                       "height": 200,
#                       "id": "7eee98cb-3f59-4a3b-b921-6a4be85af542",
#                       "legend": "fallback fip cover",
#                       "preset": "200x200",
#                       "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAgMBAAAAAAAAAAAAAAAAAgMAAQUE/8QAJBAAAgMAAQIGAwAAAAAAAAAAAAECAxEhBBIFEyIxUXEUQVL/xAAXAQEBAQEAAAAAAAAAAAAAAAAAAQIE/8QAGBEBAQADAAAAAAAAAAAAAAAAAAEDETH/2gAMAwEAAhEDEQA/AO6MBigSKGLgqA7CnDhjE0/2XgGNZQ/VNNYINp9PXz6fcD8Wr+Ea265nk6u65UUuyXOGTLxO6dmrEvg151xurcJrUzPl4Q1LYS1fDMuUzybrmpu1R49kw6pWR1Ob2LOSfQ9ZuR4X2FTX1FFvZc1jRBq1Tdlev3LF9PxW/sPSgIsNSEoJFQ3uAnCE2nJa0UQgJZFYiFEA/9k=",
#                       "src": "https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/200x200_visual-fip.jpg",
#                       "type": "image",
#                       "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/200x200_visual-fip.webp",
#                       "width": 200
#                     },
#                     "player": {
#                       "model": "EmbedImage",
#                       "author": None,
#                       "copyright": "Aucun(e)",
#                       "height": 200,
#                       "id": "7eee98cb-3f59-4a3b-b921-6a4be85af542",
#                       "legend": "fallback fip cover",
#                       "preset": "200x200",
#                       "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAgMBAAAAAAAAAAAAAAAAAgMAAQUE/8QAJBAAAgMAAQIGAwAAAAAAAAAAAAECAxEhBBIFEyIxUXEUQVL/xAAXAQEBAQEAAAAAAAAAAAAAAAAAAQIE/8QAGBEBAQADAAAAAAAAAAAAAAAAAAEDETH/2gAMAwEAAhEDEQA/AO6MBigSKGLgqA7CnDhjE0/2XgGNZQ/VNNYINp9PXz6fcD8Wr+Ea265nk6u65UUuyXOGTLxO6dmrEvg151xurcJrUzPl4Q1LYS1fDMuUzybrmpu1R49kw6pWR1Ob2LOSfQ9ZuR4X2FTX1FFvZc1jRBq1Tdlev3LF9PxW/sPSgIsNSEoJFQ3uAnCE2nJa0UQgJZFYiFEA/9k=",
#                       "src": "https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/200x200_visual-fip.jpg",
#                       "type": "image",
#                       "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2022/02/7eee98cb-3f59-4a3b-b921-6a4be85af542/200x200_visual-fip.webp",
#                       "width": 200
#                     }
#                   },
#                   "producer": "",
#                   "song": None,
#                   "stationName": "fip",
#                   "endTime": None,
#                   "media": {
#                     "sources": [
#                       {
#                         "url": "https://stream.radiofrance.fr/fip/fip.m3u8?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "hls",
#                         "bitrate": 0
#                       },
#                       {
#                         "url": "https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "aac",
#                         "bitrate": 192
#                       },
#                       {
#                         "url": "https://icecast.radiofrance.fr/fip-midfi.aac?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "aac",
#                         "bitrate": 128
#                       },
#                       {
#                         "url": "https://icecast.radiofrance.fr/fip-midfi.mp3?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "mp3",
#                         "bitrate": 128
#                       },
#                       {
#                         "url": "https://icecast.radiofrance.fr/fip-lofi.aac?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "aac",
#                         "bitrate": 32
#                       },
#                       {
#                         "url": "https://icecast.radiofrance.fr/fip-lofi.mp3?id=radiofrance",
#                         "broadcastType": "live",
#                         "format": "mp3",
#                         "bitrate": 32
#                       }
#                     ],
#                     "startTime": None,
#                     "endTime": None
#                   },
#                   "localRadios": [],
#                   "remoteDTR": 10000,
#                   "nowTime": 1691255905,
#                   "nowPercent": 0
#                 },
#                 "migrated": True,
#                 "next": {
#                   "firstLine": {
#                     "id": "ea483d20-2b2b-4977-b86c-ba576f40ccbe",
#                     "title": "Spéciales FIP",
#                     "path": "fip/podcasts/speciales-fip"
#                   },
#                   "secondLine": {
#                     "id": "84f9b539-95ac-4d33-887d-76e5d322d582",
#                     "title": "Spéciale Festival du Bout du Monde",
#                     "path": "fip/podcasts/speciales-fip/speciale-festival-du-bout-du-monde-5330990"
#                   },
#                   "thirdLine": {
#                     "id": None,
#                     "title": None,
#                     "path": None
#                   },
#                   "printProgMusic": False,
#                   "startTime": 1691260200,
#                   "producer": "",
#                   "song": None,
#                   "endTime": 1691263800
#                 }
#               }