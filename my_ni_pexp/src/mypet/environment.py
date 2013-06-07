'''
Created on 03.06.2013

@author: robert
'''
from mypet.configuration import config
from mypet.trajectory import Trajectory, SingleRun
import os
import sys
import logging
import time
import datetime
import multiprocessing as multip


def _single_run(args):

    traj=args[0] 
    logpath=args[1] 
    lock=args[2] 
    runfunc=args[3] 
    runparams = args[4]

    assert isinstance(traj, SingleRun)
    root = logging.getLogger()
    n = traj.get_n()
    #If the logger has no handler, add one:
    print root.handlers
    if len(root.handlers)<3:
        print 'do i come here?'
        filename = 'process%03d.txt' % n
        h=logging.FileHandler(filename=logpath+'/'+filename)
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h.setFormatter(f)
        root.addHandler(h)
    
    root.debug('Starting single run #%d' % n)
    result =runfunc(traj,**runparams)
    root.debug('Finished single run #%d' % n)
    traj.store_to_hdf5(lock)
    
    return result
 

    
    
class Environment(object):
    ''' The environment to run a parameter exploration.
    '''
    
    def __init__(self, trajectoryname, filename, filetitle='Experiment', dynamicly_imported_classes=[]):
        
        #Acquiring the current time
        init_time = time.time()
        thetime = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss');
        
        #For logging:
        logging.basicConfig(level=config['loglevel'])
        logpath = config['logfolder']
        
        self._logpath = os.path.join(logpath,trajectoryname+'_'+thetime)
        
        if not os.path.isdir(self._logpath):
            os.makedirs(self._logpath)
        
        
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h=logging.FileHandler(filename=self._logpath+'/main.txt')
        #sh = logging.StreamHandler(sys.stdout)
        h.setFormatter(f)
        logging.getLogger().addHandler(h)
        #logging.getLogger().addHandler(sh)

        self._traj = Trajectory(trajectoryname, filename, filetitle, dynamicly_imported_classes,init_time)
        self._logger = logging.getLogger('Environment')

        self._logger.debug('Environment initialized.')
        
    
    def _add_config(self):
        confparam=self._traj.add_parameter('Config')
        
        for key, val in config.items():
            setattr(confparam, key, val)
        
        confparam.comment = 'This parameter contains all entries of the config.'
        
    def get_trajectory(self):
        return self._traj
    
    
#     def _single_run(self,traj,runfunc, **runparams):
#         n = traj.get_n()
#         self._logger.debug('Starting single run #%d' % n)
#         result =runfunc(traj,**runparams)
#         self._logger.debug('Finished single run #%d' % n)
#         traj.store_to_hdf5()
#         return result

    def run(self, runfunc, **runparams):
        
        #Store the config file as parameters
        self._add_config()
        logpath = config['logfolder']
        #Prepares the trajecotry for running
        self._traj.prepare_experiment()
        
        multiproc = config['multiproc']

        if multiproc:
            
            lock = multip.Manager().Lock()
           
            ncores = config['ncores']
            
            mpool = multip.Pool(ncores)
        
            print '------------------'
            print 'Starting run in parallel with %d cores.' % ncores
            print '------------------'
            
            iterator = ((self._traj.make_single_run(n),self._logpath,lock,runfunc,runparams) for n in xrange(len(self._traj)))
        
            results = mpool.imap(_single_run,iterator)
            
            mpool.close()
            mpool.join()
            print '------------------'
            print 'Finished run in parallel with %d cores.' % ncores
            print '------------------'
            
            return results
        else:
            
            results = [_single_run((self._traj.make_single_run(n),self._logpath,None,runfunc,runparams)) for n in xrange(len(self._traj))]
            return results
                
        
        
        