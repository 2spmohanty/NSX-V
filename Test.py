__author__ = 'smrutim'
import pytest
import time
from NsxConfiguration.CustomLogger import CustomLogging
from NsxConfiguration.Data import config
from NsxConfiguration.Vcenter import Datacenter, VDS, Cluster, VCOps
from NsxConfiguration.NSX import NsxOperation



##########################################################################
"""

Run this as a pytest to generate Results and failure for NSX Configuration.
The test creates a log file as well as a junit style result xml, that can be feed
in Jenkins for pipeline automation.

Record the changes done, in this section for quick reference.

Dependency:
pip install pytest
pip install pytest-dependency

Run:
pytest python -m pytest Test.py -v -s --junitxml=nsxConfigTest.xml



version 1 :
Initial : Author : smrutim
Contributor: Haritej for VIB installation status.


"""

############################################################################

#Create Logger for the Test
logger = CustomLogging.generate_logger(log_file=config.LOG_FILE_NAME)



#Login to VC
@pytest.mark.dependency()
def test_Login():
    pytest.si = Datacenter.Login(logger,config.VCENTER,config.VCENTER_USER,config.VCENTER_PASSWORD)
    assert pytest.si is not None, "Getting connect Anchor to VC not successful."

#Get DC MOR
@pytest.mark.dependency(depends=["test_Login"])
def test_GetDataCenter():
    pytest.datacenter = Datacenter.GetDatacenter(config.DATCENTER_NAME, pytest.si)
    assert pytest.datacenter is not None, "Getting Datacenter Managed Object Reference Failed"




#Create DVS
@pytest.mark.dependency(depends=["test_GetDataCenter"])
@pytest.mark.skipif(config.SKIP_DVS_CREATION,reason="LDU40 DVS is created during Auto Deploy Setup")
def test_CreateDVS():
    pytest.dvsMor = VDS.CreateVDS(logger,pytest.datacenter, config.DVS_NAME, vdsVersion=config.DVS_VERSION, vdsVendor='VMware')
    assert pytest.dvsMor is not None, "DV Switch creation failed"

#Create DV Portgroup
@pytest.mark.dependency(depends=["test_CreateDVS"])
@pytest.mark.skipif(config.SKIP_DVS_PORT_CREATION,reason="LDU40 DVS Port Group is created during Auto Deploy Setup")
def test_CreateDVPortGroup():
    dvpgMorCreate = VDS.CreateDVPortgroups(pytest.datacenter, config.DVS_NAME, config.DV_PORTGROUPS
                                            , numOfPorts=128, binding='earlyBinding')
    assert dvpgMorCreate, "DV Port group creation failed."

#Add Host to DVS
@pytest.mark.dependency(depends=["test_CreateDVS","test_CreateDVPortGroup"])
@pytest.mark.skipif(config.SKIP_DVS_ADD_HOST,reason="LDU40 Host is added to DVS during Auto Deploy Setup")
def test_Add_HostToDVS():
    for clusterName in config.CLUSTER_LIST:
        logger.info("Getting Host List on Cluster " + clusterName)
        host_list = Cluster.GetHostsInCluster(pytest.datacenter, clusterName=clusterName)
        time.sleep(3)
        if host_list:
            logger.info("Adding Hosts of %s cluster to %s "%(clusterName,config.DVS_NAME))
            hostAdded = VDS.AddHostToVDS(pytest.datacenter, config.DVS_NAME, host_list, pnics=config.PNICS)
            time.sleep(3)
            assert hostAdded, "Hosts could not be added to DVS."
        else:
            continue



#Get DVS Objects
@pytest.mark.dependency(depends=["test_GetDataCenter"])
def test_Get_DVS_Mor():
    pytest.vdsObj = VDS.GetVDS(pytest.datacenter, config.DVS_NAME)
    assert pytest.vdsObj is not None, "Could not Get DVS %s MOR"%config.DVS_NAME
    pytest.dvsID = str(pytest.vdsObj).strip('\'').split(':')[1]
    assert pytest.dvsID is not None, "Could not Get DVS ID for %s." % config.DVS_NAME




#Register NSX To VC
@pytest.mark.dependency(depends=["test_Get_DVS_Mor"])
def test_Register_Nsx_To_VC():
    registration_status = NsxOperation.Register_Nsx_To_VC(logger,config.NSX_MANAGER,
                                                          config.VCENTER,config.NSX_USER,config.NSX_PASSWORD,
                                                          config.VCENTER_ROOT,config.VCENTER_ROOT_PASS)
    assert str(registration_status) == "200" , "VC Registration Unsuccessful"


#Add and Assign NSX License Key in VC
@pytest.mark.dependency(depends=["test_Register_Nsx_To_VC"])
def test_Add_NSX_Plugin_License_To_VC():
    logger.info("THREAD - Add_NSX_Plugin_License_To_VC - Adding NSX Licence in VC ")
    addLicense_Status = VCOps.AddLicense(pytest.si, config.NSX_LICENSE_KEY)
    time.sleep(10)
    assert addLicense_Status , "License could not be added to VC"
    logger.info("THREAD - Add_NSX_Plugin_License_To_VC - Assigning NSX Licence in VC ")
    assignLicense_Status = VCOps.AssignLicense(pytest.si,"nsx-netsec",config.NSX_LICENSE_KEY)
    assert assignLicense_Status , "NSX License assignment to VC failed."



#Host preparation

#Step 1: VIB Install

@pytest.mark.dependency(depends=["test_Add_NSX_Plugin_License_To_VC"])
def test_Install_VIBs():
    pytest.clusterObj = Datacenter.GetClusters(pytest.datacenter, config.CLUSTER_LIST)
    assert len(pytest.clusterObj) != 0 , "Could not get Clusters MORs."
    vib_install_status = NsxOperation.Install_VIBs(logger,config.NSX_MANAGER,pytest.clusterObj,
                                                   config.NSX_USER,config.NSX_PASSWORD)
    assert vib_install_status , "VIB Installation failure."


"""

#Put All hosts for NSX into maintenance mode
@pytest.mark.dependency(depends=["test_Install_VIBs"])
def test_Put_All_Hosts_In_Maintenance():
    maintenance_status = NsxOperation.Put_All_Hosts_In_Maintenance(logger,pytest.datacenter,config.CLUSTER_LIST)
    assert maintenance_status, "Putting All hosts in maintenance mode failed."
"""

#Check VIB Install on Hosts and Add only successful Clusters

@pytest.mark.dependency(depends=["test_Install_VIBs"])
def test_Check_Install_Vib_Status():
    clusterMoidToProceed = NsxOperation.Check_Install_Vib_Status(logger,pytest.clusterObj,
                                                        config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD)
    pytest.success_vib_install = clusterMoidToProceed
    #logger.info("The success VIB install array is " + str(pytest.success_vib_install))
    assert len(pytest.success_vib_install) != 0, "Could not get successful Clusters MORs."


"""
# Exit all hosts from maintenance mode
@pytest.mark.dependency(depends=["test_Check_Install_Vib_Status"])
def test_Exit_All_Hosts_In_Maintenance():
    maintenance_status = NsxOperation.Exit_All_Hosts_In_Maintenance(logger,pytest.datacenter,config.CLUSTER_LIST)
    assert maintenance_status, "Exit All hosts in maintenance mode failed."

"""


###VXLAN Creation. This will trigger on the clusters whose VIB install status is Green ###


@pytest.mark.dependency(depends=["test_Check_Install_Vib_Status"])
def test_Create_IP_Pool():

    pytest.ipPoolId = NsxOperation.Create_IP_Pool(logger,config.NSX_MANAGER,config.IP_POOL_NAME,config.IP_POOL_PREFIX,
                                                config.IP_POOL_GATEWAY,config.IP_POOL_DNS_SUFFIX,config.IP_POOL_DNS_1,
                                                config.IP_POOL_DNS_2,config.IP_POOL_START_ADDRESS,config.IP_POOL_END_ADDRESS,
                                                config.NSX_USER,config.NSX_PASSWORD)

    assert pytest.ipPoolId is not None, "IP Pool couldnot be created for VXLAN configuration."
    assert "ipaddresspool" in pytest.ipPoolId , "IP Pool created is invalid."


@pytest.mark.dependency(depends=["test_Create_IP_Pool"])
def test_Create_VXLAN():

    pytest.vxlan_configd_array = NsxOperation.Create_VXLAN(logger,config.NSX_MANAGER,pytest.success_vib_install,
                                                    pytest.dvsID,pytest.ipPoolId,config.NSX_USER,config.NSX_PASSWORD)

    assert len(pytest.vxlan_configd_array) != 0, "Could not initiate VXLAN configuration on any Clusters."




# This will trigger on the clusters whose VXLAN configuration is initiated
@pytest.mark.dependency(depends=["test_Create_VXLAN"])
def test_Check_Prep_Status():
    pytest.ipPoolId = "ipaddresspool-1"
    pytest.clusterObj = Datacenter.GetClusters(pytest.datacenter, config.CLUSTER_LIST)
    pytest.vxlan_configd_array = pytest.clusterObj
    pytest.success_vxlan_prepped = NsxOperation.Check_VXLAN_Vib_Status(logger,pytest.vxlan_configd_array,
                                                        config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD)

    #logger.info("THREAD - test_Check_Prep_Status -  Successful VXLAN created on " + str(pytest.success_vxlan_prepped))

    assert len(pytest.success_vxlan_prepped) != 0, "Could not get successful VXLAN prepped Clusters MORs."



#Create Transport Zone
@pytest.mark.dependency(depends=["test_Check_Prep_Status"])
def test_Create_Transport_Zone():
    pytest.vdnScope = NsxOperation.Create_Transport_Zone(logger,config.NSX_MANAGER,config.TRANSPORT_ZONE_NAME
                                                                       ,pytest.success_vxlan_prepped,
                                                         config.NSX_USER,config.NSX_PASSWORD)
    assert pytest.vdnScope is not None, "Adding Cluster to Transport Zone Failed"


#Create Segment
@pytest.mark.dependency(depends=["test_Create_Transport_Zone"])
def test_Create_Segment():
    segmentResponse = NsxOperation.Create_Segment(logger,config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD)
    assert segmentResponse == "201" , "Segment Creation Failed."


#Create Multicast
@pytest.mark.dependency(depends=["test_Create_Segment"])
def test_Configure_Multicast():
    multicastResponse = NsxOperation.Configure_Multicast(logger,config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD)
    assert multicastResponse == "201", "Multicast Configuration Failed."


#Create Virtual Wire
@pytest.mark.dependency(depends=["test_Configure_Multicast"])
def test_Create_Logical_Switch():
    pytest.logicalWire = NsxOperation.Create_Logical_Switch(logger,config.NSX_MANAGER,pytest.vdnScope,
                                                            config.LOGICAL_SWITCH,config.NSX_USER,config.NSX_PASSWORD)
    logger.info("THREAD - test_Create_Logical_Switch - The logical wire created is " + str(pytest.logicalWire))
    assert pytest.logicalWire is not None, " Logical switch creation Failed."



#Deploy Edge Router to be configured as DHCP Server for Vmotion.
@pytest.mark.dependency(depends=["test_Create_Logical_Switch"])
@pytest.mark.skipif(config.SKIP_DEPLOY_EDGE,reason="LDU19 doesnot need Edge deployment")
def test_Deploy_Edge():
    pytest.edge_location = NsxOperation.Deploy_Edge(logger,config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD,
                                                    pytest.clusterObj,config.EDGE_CLUSTER,pytest.datacenter,config.EDGE_DATASTORE,pytest.logicalWire,
                                                    config.EDGE_PRIMARY_ADDRESS,config.EDGE_SUBNET,config.EDGE_NAME)

    logger.info("THREAD - test_Deploy_Edge - The Edge deployed location is " + str(pytest.edge_location))
    assert pytest.edge_location is not None , "Deployment of Edge Failed"

#Configure OSPF Routing on the Router
@pytest.mark.dependency(depends=["test_Deploy_Edge"])
@pytest.mark.skipif(config.SKIP_EDGE_ROUTING,reason="LDU19 doesnot need Edge DLR routing")
def test_Configure_Ospf_Routing():
    configure_routing = NsxOperation.Configure_Ospf_Routing(logger,config.EDGE_PRIMARY_ADDRESS,config.NSX_MANAGER,
                                                            config.NSX_USER,config.NSX_PASSWORD,pytest.edge_location)
    assert configure_routing , "Configuring Router with OSPF routing."




#Enable and configure DHCP on Router
@pytest.mark.dependency(depends=["test_Configure_Ospf_Routing"])
@pytest.mark.skipif(config.SKIP_DHCP_CONFIGURE,reason="LDU19 doesnot need DHCP for vMotion enablement")
def test_Enable_DHCP():
    enable_dhcp = NsxOperation.Enable_DHCP(logger,config.NSX_MANAGER,config.NSX_USER,config.NSX_PASSWORD,
                                           pytest.edge_location,config.DHCP_RANGE,config.DHCP_GATEWAY,config.DHCP_SUBNET)

    assert enable_dhcp, "DHCP COnfiguration failed."


#This test add a vmk to Host and attach it to DHCP Enabled virtual wire created above
#This Test should be called only if DHCP serves the IP to vmotion nic

@pytest.mark.dependency(depends=["test_Enable_DHCP"])
@pytest.mark.skipif(config.SKIP_DHCP_ADD_NIC,reason="LDU19 need static IP for vMotion enablement")
def test_Add_nic_dhcp_enable_vmotion():
    add_nic_dhcp_enable_vmotion = NsxOperation.Add_nic_dhcp_enable_vmotion(logger,pytest.datacenter,config.DVS_NAME,
                                                                 pytest.vdsObj,
                                                                 pytest.logicalWire,config.CLUSTER_LIST)
    assert add_nic_dhcp_enable_vmotion, "Adding DHCP NIC or Enabling Vmotion failed"


#Write Tests for Adding Nic and Enabling Vmotion with Static IP Option. For LDU19 Test Bed.
@pytest.mark.dependency(depends=["test_Create_Logical_Switch"])
@pytest.mark.skipif(config.SKIP_STATIC_ADD_NIC,reason="LDU40 need DHCP IP for vMotion enablement")
def tes_Add_nic_static_enable_vmotion():
    add_nic_static_enable_vmotion = NsxOperation.Add_nic_dhcp_enable_vmotion(logger,pytest.datacenter,config.DVS_NAME,
                                                                 pytest.vdsObj,pytest.logicalWire,config.CLUSTER_LIST,
                                                                             config.STATIC_IP_ARRAY,config.STATIC_SUBNET)

    assert add_nic_static_enable_vmotion, "Adding STATIC NIC or Enabling Vmotion failed"
