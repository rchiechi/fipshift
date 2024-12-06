import socket
import base64
import threading
import logging
import time

logger = logging.getLogger(__package__+'.icecast')

class IcecastClient:
    def __init__(self, host, port, mount, username, password):
        self.host = host
        self.port = port
        self.mount = mount
        self.auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.socket = None
        self._connected = False
        self._lock = threading.Lock()
        
    def start(self):
        """Initialize connection to Icecast server"""
        logger.info(f"Attempting to connect to Icecast server at {self.host}:{self.port}{self.mount}")
        
        try:
            # Create socket with timeout
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)  # 10 second timeout
            
            # Attempt connection
            try:
                self.socket.connect((self.host, self.port))
            except socket.error as e:
                logger.error(f"Socket connection failed: {str(e)}")
                return False
            
            # Prepare headers
            headers = [
                f"PUT {self.mount} HTTP/1.1",
                f"Host: {self.host}:{self.port}",
                f"Authorization: Basic {self.auth}",
                "User-Agent: PyIcecast/1.0",
                "Content-Type: audio/aac",
                "ice-name: FipShift",
                "ice-public: 1", 
                "ice-description: Time-shifted FIP stream",
                "ice-audio-info: bitrate=256",
                "ice-genre: Eclectic",
                "Expect: 100-continue",
                "",  # Empty line required by HTTP
                ""   # Second empty line to complete headers
            ]
            
            # Send request
            request = "\r\n".join(headers).encode()
            logger.debug(f"Sending headers:\n{request.decode()}")
            
            try:
                self.socket.send(request)
            except socket.error as e:
                logger.error(f"Failed to send headers: {str(e)}")
                return False
            
            # Wait for response
            try:
                response = self.socket.recv(1024)
                if not response:
                    logger.error("Server closed connection without response")
                    return False
                    
                response_str = response.decode('utf-8', errors='replace')
                logger.debug(f"Received response:\n{response_str}")
                
                # Check for success response
                if "HTTP/1.1 200" in response_str or "HTTP/1.0 200" in response_str:
                    self._connected = True
                    logger.info("Successfully connected to Icecast server")
                    return True
                elif "401 Unauthorized" in response_str:
                    logger.error("Authentication failed - check username and password")
                    return False
                else:
                    logger.error(f"Unexpected server response: {response_str}")
                    return False
                    
            except socket.timeout:
                logger.error("Timeout waiting for server response")
                return False
            except socket.error as e:
                logger.error(f"Error receiving server response: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}", exc_info=True)
            return False
        finally:
            if not self._connected and self.socket:
                self.socket.close()
                self.socket = None
                
    def send_data(self, data):
        """Send data to Icecast server"""
        if not self._connected or not self.socket:
            return False
            
        try:
            with self._lock:
                self.socket.send(data)
            return True
        except socket.error as e:
            logger.error(f"Send failed: {str(e)}")
            self._connected = False
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
            
    def stop(self):
        """Close connection to Icecast server"""
        self._connected = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
            self.socket = None
            logger.info("Disconnected from Icecast server")
            
    @property
    def is_connected(self):
        return self._connected and self.socket is not None