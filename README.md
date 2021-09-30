# fipshift
Time shift the FIP MP3 icecast stream for listening from a different time zone.

# usage
`./shout-fip.py -d <delay time in seconds>` or `./ices-fip.py -d <delay time in seconds>`

The first time you run the script it will create a file called `fipshift.conf` in the `--configdir` directory (default ~/.config/).
Edit that file to set the server, user, password, etc.
Note that the stream will not start until the delay time has passed.

You can send `SIGHUP` to kill the file buffer, but leave the stream going until it streams the entire buffer.

`shout-fip.py` uses python-shout to start a Shoutcast mp3 server, but is really flaky.
`ices-fip.py` launches ices2 and streams to an icecast2 server, but it only streams ogg/vorbis.

# requirements

`shout-fip.py`
- [python-shout](https://pypi.org/project/python-shout/)


`ices-fip.py`
- [ices2](https://icecast.org/ices/)
- [pydub](https://pypi.org/project/pydub/)
- [icecast2](https://icecast.org/)

