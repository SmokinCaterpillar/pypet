import signal
import sys
import functools


SIGTERM = '__SIGTERM__'
terminated = False


def _handle(signum, frame):
    global terminated
    if terminated:
        sys.__stdout__.write('\nExiting immediately!\n')
        raise KeyboardInterrupt()
    else:
        terminated = True
        sys.__stdout__.write('\nYou killed the process(es) via `CTRL+C`. I am trying to exit '
                             'gracefully. Hitting `CTRL+C again will cause an immediate exit.\n')


def sigterm_handling(func):
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        if terminated:
            return (SIGTERM, None)
        current_handler = signal.getsignal(signal.SIGINT)
        if current_handler is not _handle:
            signal.signal(signal.SIGINT, _handle)
        result = func(*args, **kwargs)
        if terminated:
            result = (SIGTERM, result)
        return result
    return new_func
