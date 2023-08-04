import re

FIPBASEURL = 'https://stream.radiofrance.fr'
FIPLIST = 'https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance'
METAURL = 'https://www.radiofrance.fr/api/v2.1/stations/fip/live'
AACRE = re.compile(f'^{FIPBASEURL}/.*(fip_.*\.ts).*$')
TSRE= re.compile('(.*/fip_aac_hifi_\d_)(\d+)_(\d+)')
STRPTIME = "%Y-%m-%dT%H:%M:%SZ"
METATEMPLATE = {
                "delayToRefresh": 71000,
                "now": {
                  "firstLine": {
                    "id": None,
                    "title": "Le song",
                    "path": None
                  },
                  "secondLine": {
                    "id": None,
                    "title": "Le artist",
                    "path": None
                  },
                  "startTime": 1674841371,
                  "visuals": {
                    "card": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/250x250_rf_omm_0000232973_dnc.0057839972.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/250x250_rf_omm_0000232973_dnc.0057839972.webp",
                      "legend": None,
                      "width": 250,
                      "height": 250,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAgMEBQAB/8QAJhAAAQMDAwQCAwAAAAAAAAAAAQACAwQREiExQRMUQlEFIlJhgf/EABYBAQEBAAAAAAAAAAAAAAAAAAIAAf/EABYRAQEBAAAAAAAAAAAAAAAAAAABEf/aAAwDAQACEQMRAD8AbI/oR5OJ/qlknjey2bib7Kv5VhMAI2BWXA0iQEjRE1GVPvdwKtpakSDBhyIQlkT4rWbdL+NDI5pCXD0FNq3J/wCK77+k668v+lDpdXGJIS3k7KWpjZjGxxDdNVe4AiyxawvE9pRY8FVUVRwx62dwlQsaJDjxqUDWgR+WRTInBlO5oH2J1WE0ojlE0n0iQxOa6NuJuLIkgDkQdUFVTtqYS3y4KcAu8wsTGo2SOqOjISA3cJnQPcFhdjf3ytEtHcg2F7IZwOq02F1YWhhg7dlg4lNyHtMOyCw9LWP/2Q=="
                    },
                    "player": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/200x200_rf_omm_0000232973_dnc.0057839972.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/0683977a-2cb3-4290-ae3e-d953c83903a0/200x200_rf_omm_0000232973_dnc.0057839972.webp",
                      "legend": None,
                      "width": 200,
                      "height": 200,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAgMEBQAB/8QAJhAAAQMDAwQCAwAAAAAAAAAAAQACAwQREiExQRMUQlEFIlJhgf/EABYBAQEBAAAAAAAAAAAAAAAAAAIAAf/EABYRAQEBAAAAAAAAAAAAAAAAAAABEf/aAAwDAQACEQMRAD8AbI/oR5OJ/qlknjey2bib7Kv5VhMAI2BWXA0iQEjRE1GVPvdwKtpakSDBhyIQlkT4rWbdL+NDI5pCXD0FNq3J/wCK77+k668v+lDpdXGJIS3k7KWpjZjGxxDdNVe4AiyxawvE9pRY8FVUVRwx62dwlQsaJDjxqUDWgR+WRTInBlO5oH2J1WE0ojlE0n0iQxOa6NuJuLIkgDkQdUFVTtqYS3y4KcAu8wsTGo2SOqOjISA3cJnQPcFhdjf3ytEtHcg2F7IZwOq02F1YWhhg7dlg4lNyHtMOyCw9LWP/2Q=="
                    }
                  },
                  "producer": "",
                  "song": {
                    "id": "11cd7a76-06f5-4b5f-965d-2335a2d2930b",
                    "year": 1966,
                    "release": {
                      "label": "ATLANTIC",
                      "title": "Le album",
                      "reference": None
                    }
                  },
                  "stationName": "fip",
                  "endTime": 1674841528,
                  "media": {
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
                    ],
                    "startTime": 1674841371,
                    "endTime": 1674841528
                  },
                  "localRadios": [],
                  "remoteDTR": 71000,
                  "nowTime": 1674841458,
                  "nowPercent": 55.4140127388535
                },
                "migrated": True,
                "next": {
                  "firstLine": {
                    "id": None,
                    "title": "Fish fare",
                    "path": None
                  },
                  "secondLine": {
                    "id": None,
                    "title": "Freddie King",
                    "path": None
                  },
                  "startTime": 1674841528,
                  "visuals": {
                    "card": {
                      "src": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/2edfbbb5-2940-4f40-b0fa-0ddf188a4f92/400x400_rf_omm_0000513506_dnc.0053002059.jpg",
                      "webpSrc": "https://www.radiofrance.fr/s3/cruiser-production/2019/12/2edfbbb5-2940-4f40-b0fa-0ddf188a4f92/400x400_rf_omm_0000513506_dnc.0053002059.webp",
                      "legend": None,
                      "width": 400,
                      "height": 400,
                      "preview": "/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGQABAAMBAQAAAAAAAAAAAAAABAIDBQEA/8QAKRAAAgIBAwMDAwUAAAAAAAAAAQIAAxEEEiETIjEFQVEUI3EzNGFygf/EABgBAAMBAQAAAAAAAAAAAAAAAAECBAMA/8QAHREAAgMAAgMAAAAAAAAAAAAAAAECERIDIjEyYf/aAAwDAQACEQMRAD8AlZpXrQM1uPzOV0WuMrYD/IMs9QXr7MHtHmWaGtKiyqCM88zLI+iCae5SCznHuJw1aghsP75z8R1jhEZj7CGp6l6FrO3PjEWUUlZ1lNXWFi5szzNGDCDq7Axz84iwvHkzKfwF2ZCanrs1fgkdsvqv+ms23qVZhwYBdNdt6gWaN+na/TVFz3L5MqtMB5TvuCOc7jkxzADAHxM3RWLbrSMZCjiaVkz5F1ORWpBfxzLYWv8AUEVJ5xywp2Zaa5BWAVO4cRFeoW0bXGOIRwOeJHR87/6mWYUfALsdodPQmbaSTu45inhfS/2g/JiW8/5E5PVhQWlbTeWd1C+wEZDVj7sTJpO2E//Z"
                    },
                    "player": None
                  },
                  "producer": "",
                  "song": {
                    "id": "9bfb38ac-47e7-4ba7-a314-94d76d18166f",
                    "year": 1961,
                    "release": {
                      "label": "MODERN BLUES",
                      "title": "Just pickin'",
                      "reference": None
                    }
                  },
                  "endTime": 1674841671
                }
              }