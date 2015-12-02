import signal
import sys
import functools


SIGINT = '__SIGINT__'
terminated = False


def _handle_sigint(signum, frame):
    global terminated
    if terminated:
        prompt = 'Exiting immediately!'
        raise KeyboardInterrupt(prompt)
    else:
        terminated = True
        prompt = ('\nYou killed the process(es) via `SIGINT` (`CTRL+C`). I am trying to exit '
                  'gracefully. Using `SIGINT` (`CTRL+C`) again will cause an immediate exit.\n')
        sys.stderr.write(prompt)


def sigint_handling(add_sigterm=True):
    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            if terminated:
                if add_sigterm:
                    return (SIGINT, None)
                else:
                    return None
            current_handler = signal.getsignal(signal.SIGINT)
            if current_handler is not _handle_sigint:
                signal.signal(signal.SIGINT, _handle_sigint)
            result = func(*args, **kwargs)
            if terminated and add_sigterm:
                result = (SIGINT, result)
            return result
        return new_func
    return wrapper
