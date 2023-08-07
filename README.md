# fipshift
Time shift the FIP AAC icecast stream for listening from a different time zone.

# usage
`./fipshift.py -d <delay time in hours>`

The first time you run the script it will create a file called `fipshift.conf` in the `--configdir` directory (default ~/.config/).
Edit that file to set the server, user, password, etc.
While buffering it will relay the live fip stream and show the countdown in the stream metadata.
There will be occasional skips in the stream when it catches up (the delayed stream adds about one second per minute of delay).

# requirements

- [Requests](https://requests.readthedocs.io/en/latest/)
- [ffmpeg](https://ffmpeg.org/)
- [ices2](https://icecast.org/ices/)


