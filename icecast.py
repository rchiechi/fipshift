class Icecast(threading.Thread):

    def __init__(self, alive, lock, filequeue, **kwargs):
        threading.Thread.__init__(self)
        self.name = 'Icecast Thread'
        self.alive = alive
        self.lock = lock
        self.filequeue = filequeue
        _server = kwargs.get('server', 'http://localhost')
        _port = kwargs.get('port', '8000')
        self.iceserver = f'{_server}:{_port}'
        self.mount = kwargs.get('mount', 'fipshift')
        if self.mount[0] == '/':
            self.mount = self.mount[1:]
        self.buff = io.BytesIO()
        _auth = kwargs.get('auth', ['', ''])
        self.auth = requests.auth.HTTPBasicAuth(_auth[0], _auth[1])

    def run(self):
        logger.info('Starting %s', self.name)
        lastmeta = ''
        headers = {"Content-Type": "audio/mpeg",
                   "ice-public": "0",
                   "ice-name": "fipshift",
                   "ice-description": "Time-shifted Fip stream",
                   "ice-genre": "Eclectic",
                   "ice-bitrate": "192",
                   "ice-audio-info": "samplerate=44100;channels=2"}
        session = requests.Session()
        session.auth = self.auth
        session.headers.update(headers)
        while self.alive.is_set():
            if self.filequeue.empty():
                time.sleep(0.5)
                continue
            _fn, _meta = self.filequeue.get()
            if _meta != lastmeta:
                lastmeta = _meta
                try:
                    self.__updatemetadata(_meta)
                except requests.exceptions.ConnectionError as msg:
                    logger.warn('Metadata: %s: %s', self.name, msg)
            with self.lock:
                with open(_fn, 'rb') as fh:
                    req = session.put(f'{self.iceserver}/{self.mount}',
                                      headers=headers,
                                      data=fh,
                                      auth=self.auth)
                os.unlink(_fn)
            if req.text:
                logger.debug('Chunk: %s', req.text)
            logger.debug('Chunk %s', req.headers)
        logger.info('%s dying', self.name)


# ice-public
#     For a mountpoint that doesn't has <public> configured, this influences if the mountpoint shoult be advertised to a YP directory or not.
#     Value can either be 0 (not public) or 1 (public).
# ice-name
#     For a mountpoint that doesn't has <stream-name> configured, this sets the name of the stream.
# ice-description
#     For a mountpoint that doesn't has <stream-description> configured, this sets the description of the stream.
# ice-url
#     For a mountpoint that doesn't has <stream-url> configure, this sets the URL to the Website of the stream. (This should _not_ be the Server or mountpoint URL)
# ice-genre
#     For a mountpoint that doesn't has <genre> configure, this sets the genre of the stream.
# ice-bitrate
#     This sets the bitrate of the stream.
# ice-audio-info
#     A Key-Value list of audio information about the stream, using = as separator between key and value and ; as separator of the Key-Value pairs.
#     Values must be URL-encoded if necessary.
#     Example: samplerate=44100;quality=10%2e0;channels=2
# Content-Type
#     Indicates the content type of the stream, this must be set. 

        # req = urllib.request.Request(url='http://localhost:8080', data=DATA, method='PUT')
        # req = urllib.request.Request(url=f'{self.iceserver}/{self.mount}', data=_data, method='PUT')
        # req.add_header("Authorization", "Basic %s" % self.auth.decode('utf-8'))
        # req.add_header("Content-Type", "audio/mpeg-ts")
        # req.add_header("ice-public", "0")
        # req.add_header("ice-name", "fipshift")
        # req.add_header("ice-description", "Time-shifted Fip stream")
        # req.add_header("ice-genre", "Eclectic")
        # req.add_header("ice-bitrate", "192")
        # req.add_header("ice-audio-info", "samplerate=44100;channels=2")
        # with urllib.request.urlopen(req) as f:
        #     logger.debug('Chunk: %s', f.read().decode('utf-8'))

    def __updatemetadata(self, _meta):
        # GET /admin/metadata?pass=hackme&mode=updinfo&mount=/mp3test&song=Even%20more%20meta%21%21 HTTP/1.0
        _params = {
            'mode': 'updinfo',
            'mount': f'/{self.mount}',
            'song': _meta
        }
        _url = f'{self.iceserver}/admin/metadata?{_params}'
        req = requests.get(_url, params=_params, auth=self.auth)
        logger.debug('Metadata: %s', req.text)
        # req.add_header("Authorization", "Basic %s" % self.auth.decode('utf-8'))
        # with urllib.request.urlopen(req) as f:
        #     logger.debug('Metadata: %s', f.read().decode('utf-8'))
