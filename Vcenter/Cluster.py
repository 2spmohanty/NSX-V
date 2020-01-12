__author__ = 'smrutim'

from pyVmomi import vim
#from logging import error, warning, info, debug
from Datacenter import GetAllClusters,GetClusters,GetCluster
from VDS import wait_for_task
import time
import re
import simpleTimer
#import logging
#from threadPool import ThreadPool

"""
For Any Code changes.
Please update the READ.md file and here also for quick reference.

"""


def GetHostsInCluster(datacenter, clusterName=None, connectionState=None):
    """
    Return list of host objects from given cluster name.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterName: cluster name
    @type clusterName: string
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if clusterName != None:
        return GetHostsInClusters(datacenter, [clusterName], connectionState)
    else:
        print("clusterName is NoneType")
        return
############# Added for Register VM #####################################

def GetRunningHostsInCluster(datacenter, clusterName=None, connectionState=None):
    """
    Return list of host objects from given cluster name.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterName: cluster name
    @type clusterName: string
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if clusterName != None:
        return GetRunningHostsInClusters(datacenter, [clusterName], connectionState)
    else:
        print("clusterName is NoneType")
        return

def GetRunningHostsInClusters(datacenter, clusterNames=[], connectionState=None):
    """
    Return list of host objects from given cluster names.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: ClusterObjectMor[]
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if len(clusterNames) == 0:
        clusterObjs = GetAllClusters(datacenter)
    else:
        clusterObjs = clusterNames

    hostObjs = []
    if connectionState == None:
        hostObjs = [h for cl in clusterObjs for h in cl.host]
    else:
        hostObjs = [h for cl in clusterObjs for h in cl.host if h.runtime.connectionState == connectionState and not h.runtime.inMaintenanceMode]

    return hostObjs

def GetHostsInClusters(datacenter, clusterNames=[], connectionState=None):
    """
    Return list of host objects from given cluster names.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if len(clusterNames) == 0:
        clusterObjs = GetAllClusters(datacenter)
    else:
        clusterObjs = GetClusters(datacenter, clusterNames)

    hostObjs = []
    if connectionState == None:
        hostObjs = [h for cl in clusterObjs for h in cl.host]
    else:
        hostObjs = [h for cl in clusterObjs for h in cl.host if h.runtime.connectionState == connectionState]

    return hostObjs

