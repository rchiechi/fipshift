# fipshift
Time shift the FIP MP3 icecast stream for listening from a different time zone.

# usage
`./shout-fip.py -d <delay time in seconds>`

The first time you run the script it will create a file called `fipshift.conf` in the `--configdir` directory (default ~/.config/).
Edit that file to set the server, user, password, etc.
Note that the stream will not start until the delay time has passed.
