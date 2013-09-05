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
import pickle
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
        n = traj.get_idx()
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

    
    def __init__(self, trajectory='trajectory',
                 filename='../experiments.h5',
                 filetitle='experiment',
                 logfolder='../log/',
                 dynamically_imported_classes=None,
                 comment=''):



        #Acquiring the current time
        if isinstance(trajectory,str):
            self._traj = Trajectory(trajectory,
                                    dynamically_imported_classes=dynamically_imported_classes,
                                    comment=comment)
        elif isinstance(trajectory,Trajectory):
            self._traj = trajectory
        else:
            raise TypeError('Cannot identify your trajectory >>%s<<.' % str(trajectory))



        # Adding some default configuration
        if not self._traj.contains('config.logpath'):
            logpath = os.path.join(logfolder,self._traj.get_name())
            self._traj.ac('logpath', logpath).lock()
        else:
            logpath=self._traj.get('config.logpath').get()


        self._make_logger(logpath)


        storage_service = self._traj.get_storage_service()

        if not self._traj.contains('config.ncores'):
            self._traj.ac('ncores',1)
        if not self._traj.contains('config.multiproc'):
            self._traj.ac('multiproc',False)

        if not self._traj.contains('config.filename') and storage_service == None:
            self._traj.ac('filename',filename)
        if not self._traj.contains('config.filetitle') and  storage_service == None:
            self._traj.ac('filetitle', filetitle)

        if not self._traj.contains('config.mode'):
            self._traj.ac('mode',globally.MULTIPROC_MODE_NORMAL)

        if not self._traj.contains('config.contiuable'):
            self._traj.ac('continuable', 1)


        self._logger.info('Environment initialized.')


    def _make_logger(self,logpath):
        if not os.path.isdir(logpath):
            os.makedirs(logpath)

        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h=logging.FileHandler(filename=logpath+'/main.txt')
        #sh = logging.StreamHandler(sys.stdout)
        root = logging.getLogger()
        root.addHandler(h)

        for handler in root.handlers:
            handler.setFormatter(f)
        self._logger = logging.getLogger('mypet.environment.Environment')



    def continue_run(self, continuefile,*args,**kwargs):

        continue_dict = pickle.load(open(continuefile,'rb'))
        runfunc = continue_dict['runfunc']
        runparams = continue_dict['runparams']
        kwrunparams = continue_dict['kwrunparams']
        self._traj = continue_dict['trajectory']
        assert isinstance(self._traj,Trajectory)

        self._traj.load(load_params = globally.LOAD_NOTHING,
             load_derived_params = globally.LOAD_NOTHING,
             load_results = globally.LOAD_NOTHING,
             as_new = False)

        self._traj.load_stuff(self._traj.get_explored_parameters().values())

        self._traj.remove_incomplete_runs(*args,**kwargs)
        self._do_run(runfunc,*runparams,**kwrunparams)



        
    def get_trajectory(self):
        return self._traj


    def run(self, runfunc, *runparams,**kwrunparams):




        continuable = self._traj.get('config.continuable').get()
        logpath = self._traj.get('config.logpath').get()


        self._storage_service = self._traj.get_storage_service()




        #Prepares the trajecotry for running

        if self._storage_service == None:
            self._storage_service = HDF5StorageService(self._traj.get('config.filename').get(),
                                                 self._traj.get('config.filetitle').get() )

            self._traj.set_storage_service(self._storage_service)

        self._traj.prepare_experiment()

        if continuable:
            #HERE!
            dump_dict ={}
            if 'config.filename' in self._traj:
                filename = self._traj.get('config.filename').get()
                dump_dict['filename'] = filename
                dumpfolder= os.path.split(filename)[0]
                dumpfilename=os.path.join(dumpfolder,self._traj.get_name()+'.cnt')
            else:
                dumpfilename = os.path.join(logpath,self._traj.get_name()+'.cnt')

            dump_dict['dumpfilename'] = dumpfilename
            dump_dict['storage_service'] = self._storage_service
            dump_dict['runfunc'] = runfunc
            dump_dict['runparams'] = runparams
            dump_dict['kwrunparams'] = kwrunparams
            dump_dict['filename'] = filename
            dump_dict['trajectory'] = self._traj

            pickle.dump(dump_dict,open(dumpfilename,'wb'))

        self._do_run(runfunc,*runparams,**kwrunparams)


    def _do_run(self, runfunc, *runparams, **kwrunparams):
        logpath = self._traj.get('config.logpath').get()
        multiproc = self._traj.get('config.multiproc').get()
        mode = self._traj.get('config.mode').get()
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


            ncores =  self._traj.get('config.ncores').get()
            
            mpool = multip.Pool(ncores)

            self._logger.info('\n----------------------------------------\nStarting run in parallel with %d cores.----------------------------------------\n' %ncores)
            
            iterator = ((self._traj.make_single_run(n),logpath,queue,runfunc,len(self._traj),runparams,
                         kwrunparams) for n in xrange(len(self._traj)) if not self._traj.is_completed(n))
        
            results = mpool.imap(_single_run,iterator)

            
            mpool.close()
            mpool.join()

            if mode == globally.MULTIPROC_MODE_QUEUE:
                self._traj.get_storage_service().send_done()
                queue_process.join()

            self._logger.info('\n----------------------------------------\nFinished run in parallel with %d cores.\n----------------------------------------\n' % ncores)

            self._traj.finalize_experiment()
            self._traj.set_storage_service(self._storage_service)

            return results
        else:
            
            results = [_single_run((self._traj.make_single_run(n),logpath,None,runfunc,
                                    len(self._traj),runparams,kwrunparams)) for n in xrange(len(self._traj))
                                    if not self._traj.is_completed(n)]

            self._traj.finalize_experiment()
            return results
                
        
        
        