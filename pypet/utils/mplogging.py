
import logging


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self._logger = logger
        self._log_level = log_level
        self._linebuf = ''
 
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self._logger.log(self._log_level, line.rstrip())
    
    def flush(self):
        pass







