
import os, sys
import logging


class Config(object):
    """
    Stores all the run time configuration options. There should only
    be one instance of this object, 'config' which should be imported
    and used like a dictionary or object:

    >>> from configuration import config
    >>> config['multiproc'] = True

    
    
    """
    def __init__(self):
        self._config={}
        self.default_config()
        
    def __setstate__(self, statedict):
        self.__dict__ = statedict
        
    def __getstate__(self, statedict):
        return self.__dict__.copy()

    def default_config(self):
        self._config['multiproc'] = False
        

        ## logging
        #self._config['mplogfiles']='../log/logs.log'
        self._config['logfolder']='../log/'
        self._config['loglevel']=logging.DEBUG
    
    
    def __getitem__(self, key):
        
        if key not in self._config:
            raise AttributeError('Configuration item does not exist.')
        return self._config[key]

    def __setitem__(self, key, value):
        if key not in self._config:
            raise AttributeError('Configuration item does not exist.')
        else:
            self._config[key] = value
        
            
config = Config()
