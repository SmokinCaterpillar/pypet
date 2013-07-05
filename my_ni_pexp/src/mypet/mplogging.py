import os
import sys
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








# #!/usr/bin/env python
# # Copyright (C) 2010 Vinay Sajip. All Rights Reserved.
# #
# # Permission to use, copy, modify, and distribute this software and its
# # documentation for any purpose and without fee is hereby granted,
# # provided that the above copyright notice appear in all copies and that
# # both that copyright notice and this permission notice appear in
# # supporting documentation, and that the name of Vinay Sajip
# # not be used in advertising or publicity pertaining to distribution
# # of the software without specific, written prior permission.
# # VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# # ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# # VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# # ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# # IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# # OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
# #
# """
# An example script showing how to use logging with multiprocessing.
# 
# The basic strategy is to set up a listener process which can have any logging
# configuration you want - in this example, writing to rotated log files. Because
# only the listener process writes to the log files, you don't have file
# corruption caused by multiple processes trying to write to the file.
# 
# The listener process is initialised with a queue, and waits for logging events
# (LogRecords) to appear in the queue. When they do, they are processed according
# to whatever logging configuration is in effect for the listener process.
# 
# Other processes can delegate all logging to the listener process. They can have
# a much simpler logging configuration: just one handler, a QueueHandler, needs
# to be added to the root logger. Other loggers in the configuration can be set
# up with levels and filters to achieve the logging verbosity you need.
# 
# A QueueHandler processes events by sending them to the multiprocessing queue
# that it's initialised with.
# 
# In this demo, there are some worker processes which just log some test messages
# and then exit.
# 
# This script was tested on Ubuntu Jaunty and Windows 7.
# 
# Copyright (C) 2010 Vinay Sajip. All Rights Reserved.
# """
# # You'll need these imports in your own code
# import logging
# import logging.handlers
# import multiprocessing
# from mypet.configuration import config
# # Next two import lines for this demo only
# from random import choice, random
# import time
# 
# class QueueHandler(logging.Handler):
#     """
#     This is a logging handler which sends events to a multiprocessing queue.
#     
#     The plan is to add it to Python 3.2, but this can be copy pasted into
#     user code for use with earlier Python versions.
#     """
# 
#     def __init__(self, queue):
#         """
#         Initialise an instance, using the passed queue.
#         """
#         logging.Handler.__init__(self)
#         self.queue = queue
#         
#     def emit(self, record):
#         """
#         Emit a record.
# 
#         Writes the LogRecord to the queue.
#         """
#         try:
#             ei = record.exc_info
#             if ei:
#                 dummy = self.format(record) # just to get traceback text into record.exc_text
#                 record.exc_info = None  # not needed any more
#             self.queue.put_nowait(record)
#         except (KeyboardInterrupt, SystemExit):
#             raise
#         except:
#             self.handleError(record)
# 
# def listener_configurer():
#     root = logging.getLogger()
#     h = logging.handlers.RotatingFileHandler(config['mplogfiles'], 'a', 300000, 10)
#     f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
#     h.setFormatter(f)
#     root.addHandler(h)
# 
# # This is the listener process top-level loop: wait for logging events
# # (LogRecords)on the queue and handle them, quit when you get a None for a 
# # LogRecord.
# def listener_process(queue, configurer):
#     configurer()
#     while True:
#         try:
#             record = queue.get()
#             if record is None: # We send this as a sentinel to tell the listener to quit.
#                 break
#             logger = logging.getLogger(record.name)
#             logger.handle(record) # No level or filter logic applied - just do it!
#         except (KeyboardInterrupt, SystemExit):
#             raise
#         except:
#             import sys, traceback
#             print >> sys.stderr, 'Whoops! Problem:'
#             traceback.print_exc(file=sys.stderr)
# 
# # Arrays used for random selections in this demo
# 
# LEVELS = [logging.DEBUG, logging.INFO, logging.WARNING,
#           logging.ERROR, logging.CRITICAL]
# 
# LOGGERS = ['a.b.c', 'd.e.f']
# 
# MESSAGES = [
#     'Random message #1',
#     'Random message #2',
#     'Random message #3',
# ]
# 
# # The worker configuration is done at the start of the worker process run.
# # Note that on Windows you can't rely on fork semantics, so each process
# # will run the logging configuration code when it starts.
# def worker_configurer(queue):
#     h = QueueHandler(queue) # Just the one handler needed
#     root = logging.getLogger()
#     root.addHandler(h)
#     root.setLevel(config['loglevel']) # send all messages, for demo; no other level or filter logic applied.
# 
# # This is the worker process top-level loop, which just logs ten events with
# # random intervening delays before terminating.
# # The print messages are just so you know it's doing something!
# def worker_process(queue, configurer):
#     configurer(queue)
#     name = multiprocessing.current_process().name
#     print('Worker started: %s' % name)
#     for i in range(10):
#         time.sleep(random())
#         logger = logging.getLogger(choice(LOGGERS))
#         level = choice(LEVELS)
#         message = choice(MESSAGES)
#         logger.log(level, message)
#     print('Worker finished: %s' % name)
# 
# # Here's where the demo gets orchestrated. Create the queue, create and start
# # the listener, create ten workers and start them, wait for them to finish,
# # then send a None to the queue to tell the listener to finish.
# def main():
#     queue = multiprocessing.Queue(-1)
#     listener = multiprocessing.Process(target=listener_process,
#                                        args=(queue, listener_configurer))
#     listener.start()
#     workers = []
#     for i in range(10):
#         worker = multiprocessing.Process(target=worker_process,
#                                        args=(queue, worker_configurer))
#         workers.append(worker)
#         worker.start()
#     for w in workers:
#         w.join()
#     queue.put_nowait(None)
#     listener.join()
# 
# if __name__ == '__main__':
#     main()