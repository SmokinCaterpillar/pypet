'''
Created on 01.06.2013

@author: robert
'''
from multiprocessing import Pool
from time import time
# time.clock for cputime works incorrectly in the example,
# it doesn't take into account other threads

N = 1000
K = 5000

def cb(r): #optional: callback function
    pass
    #print r

def CostlyFunction(z):
    r = 0
    print 'juhu'
    for k in xrange(1, K+2):
        r += z ** (1 / k**1.5)
    return r

currtime = time()
for i in xrange(N):
    CostlyFunction(i)
print '1: serial: time elapsed:', time() - currtime

currtime = time()
po = Pool()
for i in xrange(N):
    po.apply_async(CostlyFunction,(i,),callback=cb)
po.close()
po.join()
print '2: parallel: time elapsed:', time() - currtime