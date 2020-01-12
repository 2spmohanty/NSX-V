__author__ = 'smrutim'

from subprocess import Popen,PIPE,STDOUT,call
import requests
import time
from NsxConfiguration.Vcenter import Datacenter, VDS, Cluster, VCOps
import xmltodict
import json
import paramiko
from pyVmomi import vim

"""
For Any Code changes.
Please update the READ.md file and here also for quick reference.

"""

def get_certificate_value(logger,vcUrl,root_user,root_pass):
    command = "openssl x509 -in /etc/vmware-vpx/ssl/rui.crt -fingerprint -sha256 -noout"
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(vcUrl, username=root_user, password=root_pass)
        cert_cmd = "openssl x509 -in /etc/vmware-vpx/ssl/rui.crt -fingerprint -sha256 -noout"
        stdin, stdout, stderr = ssh.exec_command(cert_cmd)
        while not stdout.channel.exit_status_ready():
            time.sleep(2)
        certValue = stdout.readlines()[0].strip().split('=')[-1]
        logger.info("THREAD - get_certificate_value - The Certificate for VC %s "%certValue)
        return certValue
    except Exception, e:
        logger.error("THREAD - get_certificate_value - Error while Certificate for VC %s "%str(e))
    finally:
        ssh.close()



def Register_Nsx_To_VC(logger,nsxmanager,vcUrl,username,password,root_user,root_pass):
    uri = "https://" + nsxmanager + "/api/2.0/services/vcconfig"
    ceryificateValue = get_certificate_value(logger,vcUrl,root_user,root_pass)
    ceryificateValue = ceryificateValue.rstrip()
    request_body = '''
    <vcInfo>
        <ipAddress>%(vcUrl)s</ipAddress>
        <userName>Administrator@vsphere.local</userName>
        <password>Admin!23</password>
        <certificateThumbprint>%(ceryificateValue)s</certificateThumbprint>
        <assignRoleToUser>true</assignRoleToUser>
        <pluginDownloadServer></pluginDownloadServer>
        <pluginDownloadPort></pluginDownloadPort>
    </vcInfo>
    '''
    request_body = request_body % {'vcUrl': vcUrl, 'ceryificateValue': ceryificateValue}

    logger.info("THREAD - Register_Nsx_To_VC - The xml body is %s"%request_body)
    # Request Body Format
    body_format = {'Content-Type': 'application/xml'}
    response = requests.put(uri, data=request_body, auth=(username, password), verify=False, headers=body_format)
    status = response.status_code
    logger.info("THREAD - Register_Nsx_To_VC - Status Code for VC Registration %s"%str(status))
    logger.info("THREAD - Register_Nsx_To_VC - Status Response for VC Registration %s "%response.text)
    logger.info("THREAD - Register_Nsx_To_VC - Status Content for VC Registration %s"%response.content)
    logger.info("THREAD - Register_Nsx_To_VC - Waiting for 60 seconds post VC registration with NSX.")
    time.sleep(60)
    return status


def Install_VIBs(logger,nsxmanager,clusterObj,username,password):
    logger.info("Installing VIBS")
    installNwVlzCompURI = "https://" + nsxmanager + "/api/2.0/nwfabric/configure"
    request_body = '''
    <nwFabricFeatureConfig>
        <resourceConfig>
        <resourceId>%(CLUSTERMOID)s</resourceId>
        </resourceConfig>
    </nwFabricFeatureConfig>
    '''
    logger.info("Getting all clusters managed object reference")
    for entity in clusterObj:
        clustrName = entity.name
        moId = str(entity).strip('\'').split(':')[1]
        logger.info("Installing Network Virtualization Components in cluster " + clustrName)
        nwComponentRequest = request_body % {'CLUSTERMOID': moId}
        # Request Body Format
        body_format = {'Content-Type': 'application/xml'}
        try:
            # API Call
            logger.info("THREAD - vibInstall - Initiating vib install on " + clustrName)
            response = requests.post(installNwVlzCompURI, data=nwComponentRequest, auth=(username, password),
                                     verify=False, headers=body_format)
            logger.info("THREAD - vibInstall - The Status of vib install on %s is  %s"% (clustrName,str(response.status_code)))
            logger.info("THREAD - vibInstall - The Detail of vib install on %s is  %s" % (clustrName, str(response.text)))
        except Exception, e:
            logger.error("THREAD - vibInstall - The Error during vib install on %s is  %s"% (clustrName,str(e)))

    return True


######################## Haritej Code ############################################################
def Put_All_Hosts_In_Maintenance(logger,dcMor,clusterNames):
    logger.info("THREAD - Put_All_Hosts_In_Maintenance - Getting all Hosts in clusters.")
    host_list = Cluster.GetHostsInCluster(dcMor, clusterName=clusterNames)
    logger.info("THREAD - Put_All_Hosts_In_Maintenance - Putting all Host in Maintenance Mode.")
    try:
        for j in host_list:
            j.EnterMaintenanceMode_Task(timeout=60, evacuatePoweredOffVms=False)
        return True
    except Exception, e:
        logger.error("THREAD - Put_All_Hosts_In_Maintenance - Putting all Host in Maintenance Mode failed due to %s."%str(e))
    return False

def Exit_All_Hosts_In_Maintenance(logger,dcMor,clusterNames):
    logger.info("THREAD - Put_All_Hosts_In_Maintenance - Getting all Hosts in clusters.")
    host_list = Cluster.GetHostsInCluster(dcMor, clusterName=clusterNames)
    logger.info("THREAD - Put_All_Hosts_In_Maintenance - Putting all Host in Maintenance Mode.")
    try:
        for j in host_list:
            j.ExitMaintenanceMode_Task(timeout=60)
        return True
    except Exception, e:
        logger.error("THREAD - Put_All_Hosts_In_Maintenance - Putting all Host in Maintenance Mode failed due to %s."%str(e))
    return False


def wait_for_nwfabric_green_new(logger,clusterObject,nsxmanager,username,password):

    flag_vxlanstatus = False
    vib_status = None
    host_list = []
    max_retry_count = 0
    clustrName = clusterObject.name
    cluster_moid = str(clusterObject).strip('\'').split(':')[1]
    installNwVlzCompURI = "https://" + nsxmanager + "/api/2.0/nwfabric/configure"
    body_format = {'Content-Type': 'application/xml'}
    manintenance = None
    #15 Attempts (2 Resolves)  to check if the Cluster VIB install is Green.(Total would be 15*20 = 300+90 seconds 6 mins 30 secs in worst case)
    while (max_retry_count < 16) and (flag_vxlanstatus == False):

        CheckNwVlzCompURI = "https://" + nsxmanager + "/api/2.0/nwfabric/" + "status" + "/child/" + cluster_moid
        logger.info("THREAD - wait_for_nwfabric_green_new - The URL is " + CheckNwVlzCompURI)
        response = requests.get(CheckNwVlzCompURI, auth=(username, password), verify=False)

        jsonoutput_status = json.dumps(xmltodict.parse(response.text))
        jsonoutput_status = json.loads(jsonoutput_status)

        if jsonoutput_status["resourceStatuses"] is None:
            logger.info("THREAD - wait_for_nwfabric_green_new - No Host in cluster %s. " % (clustrName))
            #In case there is no host in the
            return cluster_moid

        # The cluster Status

        vib_install_array = jsonoutput_status["resourceStatuses"]["resourceStatus"]["nwFabricFeatureStatus"]



        for feature in vib_install_array:
            if feature["featureId"] == "com.vmware.vshield.vsm.nwfabric.hostPrep":
                vib_status = feature["status"]
                logger.info("THREAD - wait_for_nwfabric_green_new - VIB Install status is %s " % vib_status)
                if feature["status"] == 'GREEN':
                    flag_vxlanstatus = True
                    break
                elif feature["status"] == 'RED' and (max_retry_count == 7 or max_retry_count == 14):
                    #Trying to Resolve the Cluster by initiating reinstall after putting Host in maintenance mode
                    #This attempt would be made twice. If the Hosts doesnot get resolved, Then it would be dropped.
                    logger.info("THREAD - Putting Hosts in cluster %s Maintenance Mode to initiate Resolve." % clustrName)
                    try:
                        manintenance = True
                        host_list = [h for cl in [clusterObject] for h in cl.host]
                        for j in host_list:
                            print("THREAD - Putting Host %s in cluster %s Maintenance Mode to initiate Resolve." % (j.name,clustrName))
                            j.EnterMaintenanceMode_Task(timeout=60, evacuatePoweredOffVms=False)
                    except Exception,e:
                        pass

                    request_body = '''
                                        <nwFabricFeatureConfig>
                                            <resourceConfig>
                                            <resourceId>%(CLUSTERMOID)s</resourceId>
                                            </resourceConfig>
                                        </nwFabricFeatureConfig>
                                        '''
                    logger.info("THREAD - wait_for_nwfabric_green_new - Resolving Cluster %s ." % clustrName)
                    nwComponentRequest = request_body % {'CLUSTERMOID': cluster_moid}
                    response = requests.post(installNwVlzCompURI, data=nwComponentRequest, auth=(username, password),
                                             verify=False, headers=body_format)
                    status = str(response.status_code)
                    if status == "200":
                        logger.info("THREAD - wait_for_nwfabric_green_new - Reinstall of Vibs in "
                                    "progress for %s."%clustrName)
                        time.sleep(45)
                    else:
                        logger.info("THREAD - wait_for_nwfabric_green_new - "
                                    "Resolving Failed for cluster %s"%clustrName)
                        return
                else:
                    time.sleep(20)
        max_retry_count = max_retry_count + 1

    if vib_status == "GREEN":
        if manintenance: #This would trigger if the hosts have been put on maintenenance for resolving
            try:
                for j in host_list:
                    j.ExitMaintenanceMode_Task(timeout=60)
            except Exception, e:
                pass
        return cluster_moid
    else:
        return



def Check_Install_Vib_Status(logger,clusterObj,nsxmanager,username,password):
    success_cluster_moid = []
    for entity in clusterObj:
        clustrName = entity.name
        logger.info("Checking VIB install status on cluster %s."%clustrName)
        #moId = str(entity).strip('\'').split(':')[1]
        successMoid = wait_for_nwfabric_green_new(logger,entity,nsxmanager,username,password)
        if successMoid:
            success_cluster_moid.append(successMoid)
    return success_cluster_moid


### VXLAN Configuration

# Create IP Pool
def Create_IP_Pool(logger,nsxmanager,poolname,prefix,gateway,dnsSuffix,dns1,dns2,
                   startAddress,endAddress,username,password):
    ipPoolURI = "https://" + nsxmanager + "/api/2.0/services/ipam/pools/scope/globalroot-0"
    ipPoolrequest = '''
    <ipamAddressPool>
    	<name>%(poolname)s</name>
    	<prefixLength>%(prefix)s</prefixLength>
    	<gateway>%(gateway)s</gateway>
    	<dnsSuffix>%(dnsSuffix)s</dnsSuffix>
    	<dnsServer1>%(dns1)s</dnsServer1>
    	<dnsServer2>%(dns2)s</dnsServer2>
    	<ipRanges>
    		<ipRangeDto>
    			<startAddress>%(startAddress)s</startAddress>
    			<endAddress>%(endAddress)s</endAddress>
    		</ipRangeDto>
    	</ipRanges>
    </ipamAddressPool>
    '''
    ipPoolRequestBody = ipPoolrequest % {'poolname':poolname,'prefix':prefix,'gateway':gateway,
                                   'dnsSuffix':dnsSuffix,'dns1':dns1,'dns2':dns2,
                                   'startAddress':startAddress,'endAddress':endAddress}

    # Request Body Format
    body_format = {'Content-Type': 'application/xml'}
    try:
        # API Call
        logger.info("THREAD - Create IP Pool - Initiating Request ")
        response = requests.post(ipPoolURI, data=ipPoolRequestBody, auth=(username, password), verify=False,
                                 headers=body_format)

        logger.info("THREAD - Create IP Pool - Status code " + str(response.status_code))
        ipPoolId = str(response.text)
        logger.info("THREAD - Create IP Pool - Response Text or ip pool id is " + ipPoolId)
        time.sleep(60)
        return ipPoolId
    except Exception, e:
        logger.error((str(e)))
        return None


# Create VXLAN

def Create_VXLAN(logger,nsxmanager,clusterMoidArray,dvsID,ipoolId,username,password):
    vxlan_created_array = []
    requestVXLANUri = "https://" + nsxmanager + "/api/2.0/nwfabric/configure"
    vxlan_request_body = '''
    <nwFabricFeatureConfig>
    	<featureId>com.vmware.vshield.vsm.vxlan</featureId>
    	<resourceConfig>
    		<resourceId>%(CLUSTERMOID)s</resourceId>
    		<configSpec class="clusterMappingSpec">
    			<switch><objectId>%(DVSMOID)s</objectId></switch>
    			<vlanId>0</vlanId>
    			<vmknicCount>1</vmknicCount>
    			<!-- ipPoolId is optional and if none is specified will assume DHCP for VTEP address assignment.-->
    			<ipPoolId>%(IPADDRESSPOOLID)s</ipPoolId>
    		</configSpec>
    	</resourceConfig>
    	<resourceConfig>
    		<resourceId>%(DVSMOID)s</resourceId>
    		<configSpec class="vdsContext">
    		<switch><objectId>%(DVSMOID)s</objectId></switch>
    		<mtu>1600</mtu>
    		<!-- teaming value can be one of FAILOVER_ORDER|ETHER_CHANNEL|LACP_ACTIVE|LACP_PASSIVE|LOADBALANCE_LOADBASE |LOADBALANCE_SRCID|LOADBALANCE_SRCMAC|LACP_V2 -->
    		<teaming>FAILOVER_ORDER</teaming>
    	</configSpec>
    	</resourceConfig>
    </nwFabricFeatureConfig>
    '''
    body_format = {'Content-Type': 'application/xml'}
    for moid in clusterMoidArray:
        #clustrName = entity.name
        logger.info("THREAD - Config VXLAN - Creating vxlan in cluster %s"%moid)
        #clusterMoId = str(entity).strip('\'').split(':')[1]
        vxlan_request_data = vxlan_request_body % {'CLUSTERMOID': moid, 'DVSMOID': dvsID,
                                                    'IPADDRESSPOOLID': ipoolId}

        try:
            # API Call
            response = requests.post(requestVXLANUri, data=vxlan_request_data, auth=(username, password), verify=False,
                                     headers=body_format)
            logger.info("THREAD - Config VXLAN -The Status of vxlan config on %s is %s"%(moid,
                                                                                         str(response.status_code)))
            if str(response.status_code) == "200":
                vxlan_created_array.append(moid)


        except Exception, e:
            logger.info("THREAD - Config VXLAN -The vxlan config on %s failed due to %s" % (moid,
                                                                                           str(e)))

    return vxlan_created_array


### VXLAN Status

def wait_for_vxlan_green_new(logger,clusterObject,nsxmanager,username,password):

    flag_vxlanstatus = False
    vib_status = None
    host_list = []
    max_retry_count = 0
    clustrName = clusterObject.name
    cluster_moid = str(clusterObject).strip('\'').split(':')[1]
    installNwVlzCompURI = "https://" + nsxmanager + "/api/2.0/nwfabric/configure"
    body_format = {'Content-Type': 'application/xml'}
    manintenance = None
    #15 Attempts (2 Resolves)  to check if the Cluster VIB install is Green.(Total would be 15*20 = 300+90 seconds 6 mins 30 secs in worst case)
    while (max_retry_count < 16) and (flag_vxlanstatus == False):

        CheckNwVlzCompURI = "https://" + nsxmanager + "/api/2.0/nwfabric/" + "status" + "/child/" + cluster_moid
        logger.info("THREAD - wait_for_vxlan_green_new - The URL is " + CheckNwVlzCompURI)
        response = requests.get(CheckNwVlzCompURI, auth=(username, password), verify=False)

        jsonoutput_status = json.dumps(xmltodict.parse(response.text))
        jsonoutput_status = json.loads(jsonoutput_status)

        if jsonoutput_status["resourceStatuses"] is None:
            logger.info("THREAD - wait_for_vxlan_green_new - No Host in cluster %s. " % (clustrName))
            #In case there is no host in the
            return cluster_moid

        # The cluster Status

        vib_install_array = jsonoutput_status["resourceStatuses"]["resourceStatus"]["nwFabricFeatureStatus"]


        for feature in vib_install_array:
            if feature["featureId"] == "com.vmware.vshield.vsm.vxlan":
                vib_status = feature["status"]
                logger.info("THREAD - wait_for_nwfabric_green_new - VIB Install status is %s " % vib_status)
                if feature["status"] == 'GREEN':
                    flag_vxlanstatus = True
                    break
                else:
                    time.sleep(30)
        max_retry_count = max_retry_count + 1

    if vib_status == "GREEN":
        if manintenance: #This would trigger if the hosts have been put on maintenenance for resolving
            try:
                for j in host_list:
                    j.ExitMaintenanceMode_Task(timeout=60)
            except Exception, e:
                pass
        logger.info("THREAD - wait_for_vxlan_green_new - The VXLAN Status is green for " + cluster_moid)
        return cluster_moid
    else:
        return


def Check_VXLAN_Vib_Status(logger,clusterObj,nsxmanager,username,password):
    success_vxlan_cluster_moid = []
    for moId in clusterObj:

        logger.info("THREAD - Check_VXLAN_Vib_Status - Checking VXLAN config status on cluster %s." % moId)
        successMoid = wait_for_vxlan_green_new(logger, moId, nsxmanager, username, password)
        if successMoid:
            success_vxlan_cluster_moid.append(successMoid)
    return success_vxlan_cluster_moid


def Create_Transport_Zone(logger,nsxmanager,transportZone,clusterMoids,username,password):
    transportZoneURI = "https://" + nsxmanager + "/api/2.0/vdn/scopes"
    logger.info("THREAD - Create_Transport_Zone - Create Transport Zone initiated.")
    transportZoneRequestBody = '''
    <vdnScope>
        <name>%(TransportZoneName)s</name>
    	<clusters>
    		%(clusterSequenceMoid)s
    	</clusters>
    	<virtualWireCount>1</virtualWireCount>
        <controlPlaneMode>MULTICAST_MODE</controlPlaneMode>
    </vdnScope>
    '''

    clusterMoid = '''<cluster><cluster><objectId>%(clusmorid)s</objectId></cluster></cluster>
                    '''

    clusterData = ""

    body_format = {'Content-Type': 'application/xml'}

    for moId in clusterMoids:
        clusterData = clusterData + clusterMoid % {'clusmorid': moId}

    transportZoneRequestBodyData = transportZoneRequestBody % {'TransportZoneName':transportZone, 'clusterSequenceMoid': clusterData.rstrip('   \n')}

    response = requests.post(transportZoneURI, data=transportZoneRequestBodyData, auth=(username, password),
                             verify=False, headers=body_format)
    logger.info("THREAD - Create_Transport_Zone - The Status of transport zone creation config is " + str(response.status_code))
    scopeID = response.text  # to be used by Logical Switch Creation
    logger.debug("THREAD - Create_Transport_Zone - The details of transport zone creation (scope ID) request is " + response.text)

    time.sleep(30)
    if scopeID and str(response.status_code)=="201":
        return scopeID.strip()
    else:
        return


def Create_Segment(logger,nsxmanager,username,password):
    segment_requestURI = "https://" + nsxmanager + "/api/2.0/vdn/config/segments"
    logger.info("THREAD - Create_Segment - Creating Segment")
    segment_request_Body = '''
    	<segmentRange>
    		<id>1</id>
    		<name>nsx-segment</name>
    		<desc>Segment for NSX ST Test</desc>
    		<begin>5000</begin>
    		<end>10000</end>
    	</segmentRange>
    '''
    body_format = {'Content-Type': 'application/xml'}
    response = requests.post(segment_requestURI, data=segment_request_Body, auth=(username, password), verify=False,
                             headers=body_format)
    response_status = str(response.status_code)
    logger.info("THREAD - Create_Segment - The Status of Segment creation config is " + response_status)

    return str(response_status)

def Configure_Multicast(logger,nsxmanager,username,password):
    multicast_uri = "https://" + nsxmanager + "/api/2.0/vdn/config/multicasts"
    multicast_request_Body = '''
    <multicastRange>
    	<id>2</id>
    	<name>nsxv-mac</name>
    	<desc>Multicast Address Range for VCST NSX Tests</desc>
    	<begin>239.1.1.1</begin>
    	<end>239.1.100.100</end>
    </multicastRange>
    '''
    body_format = {'Content-Type': 'application/xml'}
    response = requests.post(multicast_uri, data=multicast_request_Body, auth=(username, password), verify=False,
                             headers=body_format)
    multicast_status = response.status_code
    logger.info("The Status of Multicast creation config is " + str(multicast_status))
    logger.debug("The details of Multicast  creation request is " + response.text)

    time.sleep(30)
    return str(multicast_status)

def Create_Logical_Switch(logger,nsxmanager,vdnscopeValue,logicalSwitch,username,password):
    virtual_wire_request_URI = "https://" + nsxmanager + "/api/2.0/vdn/scopes/" + vdnscopeValue + "/virtualwires"
    logger.info("THREAD - Create_Logical_Switch - Starting creation of Logical Wire")
    virtual_wire_request = '''
    <virtualWireCreateSpec>
    	<name>%(logicalSwitch)s</name>
    	<description>Logical switch creation</description>
    	<tenantId>virtual wire tenant</tenantId>
    	<controlPlaneMode>MULTICAST_MODE</controlPlaneMode>
    </virtualWireCreateSpec>
    '''
    virtual_wire_request_body = virtual_wire_request % {'logicalSwitch': logicalSwitch}
    body_format = {'Content-Type': 'application/xml'}
    response = requests.post(virtual_wire_request_URI, data=virtual_wire_request_body,
                             auth=(username, password), verify=False, headers=body_format)
    virtual_wire_response = str(response.status_code)
    virtual_wire = response.text.strip()
    logger.info("THREAD - Create_Logical_Switch - The Status of virtual wire " + logicalSwitch + " creation is " + virtual_wire_response)
    logger.info("THREAD - Create_Logical_Switch - The details of virtual wire " + logicalSwitch + " creation is " + virtual_wire)

    time.sleep(30)
    if virtual_wire_response == "200" or virtual_wire_response == "201":
        return virtual_wire
    else:
        return

#Deploy Edge

def Deploy_Edge(logger,nsxmanager,username,password,clusterObjs,clusterName,dcMor,dataStoreName,
                portGroupMor,primaryAddressIp,subNet,edgeName):
    edge_request_URI = "https://" + nsxmanager + "/api/4.0/edges/"


    logger.info("THREAD - Deploy_Edge - Deployment of Edge Started %s"%edge_request_URI)
    resourcePoolMor = None

    for clusterObj in clusterObjs:
        if clusterObj.name == clusterName:
            resourcePoolMor = clusterObj.resourcePool

    resourcePoolMor = str(resourcePoolMor).strip('\'').split(':')[1]
    logger.info("THREAD - Deploy_Edge - The resource pool is " + str(resourcePoolMor))

    datastoreMor = None
    datastoresMors = dcMor.datastore

    for datastore in datastoresMors:
        if datastore.info.name in dataStoreName:
            datastoreMor = datastore

    datastoreMor = str(datastoreMor).strip('\'').split(':')[1]
    logger.info("THREAD - Deploy_Edge - The datacenter is " + str(datastoreMor))

    edge_request_body = '''
    <edge>
       <name>%(edgeName)s</name>
       <datacenterMoid>%(dataCenter)s</datacenterMoid>
       <description>Smruti Router</description>
       <appliances>
          <applianceSize>compact</applianceSize>
          <appliance>
             <resourcePoolId>%(resourcePoolMor)s</resourcePoolId>
             <datastoreId>%(datastoreMor)s</datastoreId>
          </appliance>
       </appliances>
       <vnics>
          <vnic>
             <index>0</index>
             <type>internal</type>
             <portgroupId>%(portGroupMor)s</portgroupId>
             <addressGroups>
                <addressGroup>
                   <primaryAddress>%(primaryAddressIp)s</primaryAddress>
                   <subnetMask>%(subNet)s</subnetMask>
                </addressGroup>
             </addressGroups>
             <mtu>1500</mtu>
             <isConnected>true</isConnected>
          </vnic>
       </vnics>
       <features>
          <firewall>
             <defaultPolicy>
                <action>accept</action>
                <loggingEnabled>false</loggingEnabled>
             </defaultPolicy>
          </firewall>
       </features>
    </edge>
    '''

    dataCenter = str(dcMor).strip('\'').split(':')[1]

    edge_request_body = edge_request_body % {'edgeName': edgeName, 'dataCenter': dataCenter,
                                             'resourcePoolMor': resourcePoolMor,
                                             'datastoreMor': datastoreMor,
                                             'portGroupMor': portGroupMor, 'primaryAddressIp': primaryAddressIp,
                                             'subNet': subNet}

    #logger.info("THREAD - Deploy_Edge - The XML requestbody of Edge Installation is \n" + edge_request_body_x)

    body_format = {'Content-Type': 'application/xml'}


    response = requests.post(edge_request_URI, data=edge_request_body, auth=(username, password), verify=False, headers=body_format)

    edge_response_status = str(response.status_code)

    logger.info("THREAD - Deploy_Edge - The Status of Edge Installation is "  + str(edge_response_status))


    if edge_response_status == "200" or edge_response_status == "201":
        header = response.headers
        location = header.get('Location', None)
        return location
    else:
        return None


def Configure_Ospf_Routing(logger,routerId,nsxmanager,username,password,location):
    logger.info("THREAD - Configure_Ospf_Routing - Configuring OSPF routing.")
    ospf_xml = '''
    <routing>
       <routingGlobalConfig>
          <routerId>%(routerId)s</routerId>
       </routingGlobalConfig>
       <ospf>
          <enabled>true</enabled>
          <ospfAreas>
             <ospfArea>
                <areaId>100</areaId>
             </ospfArea>
          </ospfAreas>
          <ospfInterfaces>
             <ospfInterface>
                <vnic>0</vnic>
                <areaId>100</areaId>
                <mtuIgnore>false</mtuIgnore>
             </ospfInterface>
          </ospfInterfaces>
          <redistribution>
             <enabled>true</enabled>
             <rules>
                <rule>
                   <from>
                      <isis>false</isis>
                      <ospf>true</ospf>
                      <bgp>true</bgp>
                      <static>true</static>
                      <connected>true</connected>
                   </from>
                   <action>permit</action>
                </rule>
             </rules>
          </redistribution>
       </ospf>
    </routing>
    '''
    body_format = {'Content-Type': 'application/xml'}
    ospf_xml = ospf_xml % {'routerId': routerId}
    ospf_config_uri = "https://" + nsxmanager + location + "/routing/config"
    response = requests.put(ospf_config_uri, data=ospf_xml, auth=(username, password),
                            verify=False, headers=body_format)
    status_code = str(response.status_code)
    logger.info("THREAD - Configure_Ospf_Routing - The Status of ospf config is " + status_code)

    if status_code == "204":
        return True
    else:
        return False




def Enable_DHCP(logger,nsxmanager,username, password,location,ipRange,defaultGateway,subnetMask):
    dhcp_uri = "https://" + nsxmanager + location + "/dhcp/config"

    dhcp_edge_req_body = '''
    <dhcp>
        <enabled>true</enabled>
        <ipPools>
            <ipPool>
                <ipRange>%(ipRange)s</ipRange>
                <defaultGateway>%(defaultGateway)s</defaultGateway>
                <subnetMask>%(subnetMask)s</subnetMask>
            </ipPool>
        </ipPools>
    </dhcp>
    '''

    dhcp_edge_req_body = dhcp_edge_req_body % {'ipRange': ipRange, 'defaultGateway': defaultGateway,
                                               'subnetMask': subnetMask}

    logger.info("THREAD - Enable_DHCP - Deploying DHCP Service on edge")
    body_format = {'Content-Type': 'application/xml'}
    response = requests.put(dhcp_uri, data=dhcp_edge_req_body,
                            auth=(username, password), verify=False, headers=body_format)
    status_code = str(response.status_code)
    logger.info("THREAD - Enable_DHCP - The Status of DHCP Installation is " + status_code)

    if status_code == "204":
        return True
    else:
        return False



def Add_nic_dhcp_enable_vmotion(logger,dcMor,dvSwitch,dvsMor,virtualwire,clusterNameArray):

    try:

        pg = VDS.getPortName(dcMor, virtualwire, vdsName=dvSwitch)
        pgKey = None
        for item in pg:
            pgKey = item.key
        vms = vim.host.VMotionSystem

        dvsUuid = dvsMor.uuid

        host_list = Cluster.GetHostsInClusters(dcMor, clusterNameArray, connectionState='connected')
        for h in host_list:
            logger.info("THREAD - Add_nic_enable_vmotion - Trying to add nic to " + h.name)

            hostNetworkSys = h.configManager.networkSystem
            vMotionSystem = h.configManager.vmotionSystem

            vmnicSpec = vim.host.VirtualNic.Specification()

            # Nic Specification

            ipSpec = vim.host.IpConfig()
            ipSpec.dhcp = True

            vmnicSpec.ip = ipSpec

            # DVPort Specification


            dvpgSpec = vim.dvs.PortConnection()
            dvpgSpec.switchUuid = dvsUuid
            dvpgSpec.portgroupKey = pgKey

            vmnicSpec.distributedVirtualPort = dvpgSpec

            try:

                vmkid = hostNetworkSys.AddVirtualNic("", vmnicSpec)

                logger.info("THREAD - Add_nic_enable_vmotion - Enabling vmotion on vmknic " + vmkid + " for " + h.name)

                vMotionSystem.SelectVnic(vmkid)

            except Exception,e:
                logger.error("Failure while Adding Nic and Enabling Vmotion for Host "+ h.name)


    except Exception,e:
        logger.error("Failure while Geeting DVS or port details for adding to Host " + str(e))
        return False

    return True

def Add_nic_static_enable_vmotion(logger,dcMor,dvSwitch,dvsMor,virtualwire,clusterNameArray,staticIpArray,subnetMask):
    try:

        pg = VDS.getPortName(dcMor, virtualwire, vdsName=dvSwitch)
        pgKey = None
        for item in pg:
            pgKey = item.key
        vms = vim.host.VMotionSystem

        dvsUuid = dvsMor.uuid

        host_list = Cluster.GetHostsInClusters(dcMor, clusterNameArray, connectionState='connected')
        i = 0
        for h in host_list:
            logger.info("THREAD - Add_nic_enable_vmotion - Trying to add nic to " + h.name)

            hostNetworkSys = h.configManager.networkSystem
            vMotionSystem = h.configManager.vmotionSystem

            vmnicSpec = vim.host.VirtualNic.Specification()

            # Nic Specification

            ipSpec = vim.host.IpConfig()
            ipSpec.ipAddress = staticIpArray[i]
            ipSpec.subnetMask = subnetMask
            ipSpec.dhcp = False

            vmnicSpec.ip = ipSpec

            # DVPort Specification


            dvpgSpec = vim.dvs.PortConnection()
            dvpgSpec.switchUuid = dvsUuid
            dvpgSpec.portgroupKey = pgKey

            vmnicSpec.distributedVirtualPort = dvpgSpec

            try:

                vmkid = hostNetworkSys.AddVirtualNic("", vmnicSpec)

                logger.info("THREAD - Add_nic_enable_vmotion - Enabling vmotion on vmknic " + vmkid + " for " + h.name)

                vMotionSystem.SelectVnic(vmkid)


            except Exception,e:
                logger.error("Failure while Adding Nic and Enabling Vmotion for Host "+ h.name)

            i = i+1 # Incrementing the IpArray for next IP


    except Exception,e:
        logger.error("Failure while Geeting DVS or port details for adding to Host " + str(e))
        return False

    return True













