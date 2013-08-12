'''
Created on 03.06.2013

@author: robert
'''
from Cython.Runtime.refnanny import loglevel

from mypet.mplogging import StreamToLogger
from mypet.trajectory import Trajectory, SingleRun
import os
import sys
import logging
import time
import datetime
import multiprocessing as multip
import traceback
from mypet.storageservice import HDF5StorageService, QueueStorageServiceSender,QueueStorageServiceWriter, LockWrapper
from  mypet import globally

def _single_run(args):

    try:
        traj=args[0] 
        logpath=args[1] 
        queue=args[2]
        runfunc=args[3] 
        total_runs = args[4]
        runparams = args[5]
        kwrunparams = args[6]
    
        assert isinstance(traj, SingleRun)
        root = logging.getLogger()
        n = traj.get_n()
        #If the logger has no handler, add one:
        #print root.handlers
        if len(root.handlers)<3:
            
            #print 'do i come here?'

            filename = 'process%03d.txt' % n
            h=logging.FileHandler(filename=logpath+'/'+filename)
            f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
            h.setFormatter(f)
            root.addHandler(h)
    
            #Redirect standard out and error to the file
            outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
            sys.stdout = outstl

            errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
            sys.stderr = errstl
            
            
        outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
        sys.stdout = outstl

        ## Add the queue for storage
        if not queue == None:
            traj.get_storage_service().set_queue(queue)
    
        root.info('\n--------------------------------\n Starting single run #%d of %d \n--------------------------------' % (n,total_runs))
        result =runfunc(traj,*runparams,**kwrunparams)
        root.info('Evoke Storing (Either storing directly or sending trajectory to queue)')
        traj.store()
        root.info('\n--------------------------------\n Finished single run #%d of %d \n--------------------------------' % (n,total_runs))
        return result

    except:
        errstr = "\n\n########## ERROR ##########\n"+"".join(traceback.format_exception(*sys.exc_info()))+"\n"
        logging.getLogger('STDERR').error(errstr)
        raise Exception("".join(traceback.format_exception(*sys.exc_info())))

def _queuehandling(handler):
    handler.run()

class Environment(object):
    ''' The environment to run a parameter exploration.
    '''

    
    def __init__(self, trajectoryname,
                 filename='../Experiments',
                 filetitle='Experiment',
                 dynamicly_imported_classes=None,
                 logfolder='../log/'):
        
        #Acquiring the current time
        init_time = time.time()
        thetime = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss');
        
        # Logging
        self._logpath = os.path.join(logfolder,trajectoryname+'_'+thetime)

        self._storage_set = False
        
        if not os.path.isdir(self._logpath):
            os.makedirs(self._logpath)
        
        
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h=logging.FileHandler(filename=self._logpath+'/main.txt')
        #sh = logging.StreamHandler(sys.stdout)
        root = logging.getLogger()
        root.addHandler(h)



        for handler in root.handlers:
            handler.setFormatter(f)
        self._logger = logging.getLogger('mypet.environment.Environment')


        # Creating the Trajectory
        self._traj = Trajectory(trajectoryname, dynamicly_imported_classes,init_time)

        # Adding some default configuration
        self._traj.ac('logpath', self._logpath).lock()
        self._traj.ac('ncores',1)
        self._traj.ac('multiproc',False)
        self._traj.ac('filename',filename)
        self._traj.ac('filetitle', filetitle)
        self._traj.ac('mode',globally.MULTIPROC_MODE_NORMAL)


        self._storage_service = HDF5StorageService(self._traj.get('Config.filename').get(),
                                                 self._traj.get('Config.filetitle').get() )

        self._logger.debug('Environment initialized.')



        
    def get_trajectory(self):
        return self._traj

    def change_storage_service(self,service):
        self._storage_service = service

    def get_storage_service(self):
        return self._storage_service

    def run(self, runfunc, *runparams,**kwrunparams):
        

        #Prepares the trajecotry for running

        self._traj.set_storage_service(self._storage_service)
        self._traj.prepare_experiment()


        multiproc = self._traj.get('Config.multiproc').get()
        mode = self._traj.get('Config.mode').get()
        if multiproc:
            if mode == globally.MULTIPROC_MODE_QUEUE:
                manager = multip.Manager()
                queue = manager.Queue()
                self._logger.info('Starting the Storage Queue!')
                queue_writer = QueueStorageServiceWriter(self._storage_service,queue)

                queue_process = multip.Process(name='QueueProcess',target=_queuehandling, args=(queue_writer,))
                queue_process.daemon=True
                queue_process.start()

                queue_sender = QueueStorageServiceSender()
                queue_sender.set_queue(queue)
                self._traj.set_storage_service(queue_sender)

            elif mode == globally.MULTIPROC_MODE_NORMAL:
                manager = multip.Manager()
                lock = manager.RLock()
                queue = None

                lock_wrapper = LockWrapper(self._storage_service,lock)
                self._traj.set_storage_service(lock_wrapper)

            else:
                raise RuntimeError('The mutliprocessing mode %s, you chose is not supported, use %s or %s.'
                                    %(globally.MULTIPROC_MODE_QUEUE, globally.MULTIPROC_MODE_NORMAL))


            ncores =  self._traj.get('Config.ncores').get()
            
            mpool = multip.Pool(ncores)

            self._logger.info('\n----------------------------------------\nStarting run in parallel with %d cores.----------------------------------------\n' %ncores)
            
            iterator = ((self._traj.make_single_run(n),self._logpath,queue,runfunc,len(self._traj),runparams,
                         kwrunparams) for n in xrange(len(self._traj)))
        
            results = mpool.imap(_single_run,iterator)
            
            mpool.close()
            mpool.join()

            if mode == globally.MULTIPROC_MODE_QUEUE:
                self._traj.get_storage_service().send_done()
                queue_process.join()

            self._logger.info('\n----------------------------------------\nFinished run in parallel with %d cores.\n----------------------------------------\n' % ncores)

            return results
        else:
            
            results = [_single_run((self._traj.make_single_run(n),self._logpath,None,runfunc,
                                    len(self._traj),runparams,kwrunparams)) for n in xrange(len(self._traj))]
            return results
                
        
        
        