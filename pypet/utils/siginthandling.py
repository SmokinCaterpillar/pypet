"""Module that handles KeyboardInterrupt to exit gracefully"""

__author__ = 'Robert Meyer'

import signal
import sys


class _SigintHandler(object):

    SIGINT = '__SIGINT__'

    def __init__(self):
        self.original_handler = signal.getsignal(signal.SIGINT)
        self.hit = False  # variable to signal if SIGINT has been encountered before
        self.started = False

    def start(self):
        if not self.started:
            signal.signal(signal.SIGINT, self._handle_sigint)
            self.started = True

    def finalize(self):
        self.hit = False
        self.started = False
        signal.signal(signal.SIGINT, self.original_handler)

    def _handle_sigint(self, signum, frame):
        """Handler of SIGINT

        Does nothing if SIGINT is encountered once but raises a KeyboardInterrupt in case it
        is encountered twice.
        immediatly.

        """
        if self.hit:
            prompt = 'Exiting immediately!'
            raise KeyboardInterrupt(prompt)
        else:
            self.hit = True
            prompt = ('\nYou killed the process(es) via `SIGINT` (`CTRL+C`). '
                      'I am trying to exit '
                      'gracefully. Using `SIGINT` (`CTRL+C`) '
                      'again will cause an immediate exit.\n')
            sys.stderr.write(prompt)

sigint_handling = _SigintHandler()


