__author__ = 'smrutim'

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
import getpass
from logging import error, warning, info, debug
import re
import ssl
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

"""
For Any Code changes.
Please update the READ.md file and here also for quick reference.

"""

def Login(host, user, pwd, port=443):

    context = ssl._create_unverified_context()
    si = SmartConnect(host=host,user=user,pwd=pwd,port=port,sslContext=context)
    atexit.register(Disconnect, si)
    return si

def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print "there was an error"
            task_done = True

"""
def Logout(si):
    SmartConnect.Disconnect(si)
"""

def AddLicense(si, licensekey):
    licenseManager = si.RetrieveContent().licenseManager
    licenseManager.AddLicense(licensekey)
    return True

def AssignLicense(si, entity, licensekey):
    try:
        licenseAssignmentManager = si.RetrieveContent().licenseManager.licenseAssignmentManager
        licenseAssignmentManager.UpdateAssignedLicense(entity, licensekey)
        return True
    except Exception, e:
        print str(error(e))
        raise


def AssignVCLicense(si, licensekey):
    vcEntity = si.content.about.instanceUuid
    AssignLicense(si, vcEntity, licensekey)


def AddVCPermission(si, principal, roleLabel = "Administrator", group=False, propagate=True):
    entity = si.RetrieveContent().GetRootFolder()
    AddPermission(si, entity, principal, roleLabel, group, propagate)

def AddPermission(si, entity, principal, roleLabel = "Read-only", group=False, propagate=True):
    try:
        authManager = si.RetrieveContent().GetAuthorizationManager()
        roleId = GetRoleId(si, roleLabel)

        permissions = []
        permissions.append(vim.AuthorizationManager.Permission(
                                                             entity = entity,
                                                             principal=principal,
                                                             group=group,
                                                             roleId= roleId,
                                                             propagate = propagate))
        authManager.SetEntityPermissions(entity, permissions)
    except Exception, e:
        error("Add permission failed: %s" %e)

def AddPermissions(si, entity, principal=[], roleLabel = "Read-only", group=False, propagate=True):
    try:
        authManager = si.RetrieveContent().GetAuthorizationManager()
        roleId = GetRoleId(si, roleLabel)

        permissions = []
        for p in principal:
            permissions.append(vim.AuthorizationManager.Permission(
                                                             entity = entity,
                                                             principal=p,
                                                             group=group,
                                                             roleId= roleId,
                                                             propagate = propagate))
        authManager.SetEntityPermissions(entity, permissions)
    except Exception, e:
        error("Add permission failed: %s" %e)

def GetRoleId(si, roleLabel):
    authManager = si.RetrieveContent().GetAuthorizationManager()
    roles = authManager.GetRoleList()

    for role in roles:
        if role.info.label == roleLabel:
            return role.roleId

    error("%s is not the correct role lable" %roleLabel)
    return None

def GetSessionList(si):
    return si.content.sessionManager.sessionList

def GetServiceEndpoint(si):
    return si.RetrieveInternalContent().GetServiceDirectory().QueryServiceEndpointList()


