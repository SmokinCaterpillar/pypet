"""Module that handles KeyboardInterrupt to exit gracefully"""


__author__ = 'Robert Meyer'


import signal
import sys


class _SigintHandler(object):

    SIGINT = '__SIGINT__'

    def __init__(self):
        self.original_handler = signal.getsignal(signal.SIGINT)
        self.terminated = False  # variable to signal if SIGINT has been encountered before

    def finalize(self):
        self.terminated = False
        signal.signal(signal.SIGINT, self.original_handler)

    def _handle_sigint(self, signum, frame):
        """Handler of SIGINT

        Does nothing if SIGINT is encountered once but raises a KeyboardInterrupt in case it
        is encountered twice.
        immediatly.

        """
        if self.terminated:
            prompt = 'Exiting immediately!'
            raise KeyboardInterrupt(prompt)
        else:
            self.terminated = True
            prompt = ('\nYou killed the process(es) via `SIGINT` (`CTRL+C`). I am trying to exit '
                      'gracefully. Using `SIGINT` (`CTRL+C`) again will cause an immediate exit.\n')
            sys.stderr.write(prompt)

    def __call__(self, exit_graceful, add_sigint, func, *args, **kwargs):
        """Allows a function to end gracefully on SIGINT (CTRL+C).

        All further calls of the wrapped function will return `None` immediately as soon as
        SIGINT is encountered once.

        :return:

            ``('__SIGINT__', result)```result`` is ``None`` if function
            is called again after a SIGINT.

        """
        if exit_graceful:
            if signal.getsignal(signal.SIGINT) is not self._handle_sigint:
                signal.signal(signal.SIGINT, self._handle_sigint)
            #sys.__stdout__.write('HA %s' % signal.getsignal(signal.SIGINT))
            if self.terminated:
                if add_sigint:
                    return (self.SIGINT, None)
                else:
                    return None
            result = func(*args, **kwargs)
            if self.terminated and add_sigint:
                result = (self.SIGINT, result)
            return result
        else:
            #sys.__stdout__.write('HERE %s func %s' % (signal.getsignal(signal.SIGINT), func.__name__))
            return func(*args, **kwargs)


sigint_handling = _SigintHandler()


