
import sys
import socket
import logging
import os
import time
import signal
import subprocess
import random
import struct
import binascii
import re
import json
import urllib2

try:
    import scapy.all as scapy
except:
    try:
        import scapy as scapy
    except:
        sys.exit("Need to install scapy for packet parsing")

import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action
import oftest.parse as parse
import oftest.fakedevice as fakedevice

global skipped_test_count
skipped_test_count = 0

ETHERTYPE_IP = 0x800
ETHERTYPE_ARP = 0x806
ARP_REQ = 1
ARP_REPLY = 2
IPPROTO_ICMP = socket.IPPROTO_ICMP
ECHO_REQUEST = 0x3

ETHERTYPE_LLDP = 0x88cc
CHASSISID_TYPE = 1
PORTID_TYPE = 2
TTL_TYPE = 3

# Values in config file (tests-base.xml)

OFPORT = 16633
RPCPORT = 18080
CTLPORT_OFFSET = 54321
OFFSET = 1
CONFIG_FILE = "tests-base.json"

SRC_MAC_FOR_CTL0_0 = "00:00:00:00:00:02"
SRC_MAC_FOR_CTL0_1 = "00:01:00:00:00:02"
SRC_MAC_FOR_CTL1_0 = "00:00:00:00:00:01"
SRC_MAC_FOR_CTL1_1 = "00:01:00:00:00:01"

NUM_FLOWSPACE_IN_CONF_FILE = 10
NUM_LINK_IN_CONF_FILE = 2
EXIST_ID_IN_CONF_FILE = "1000"
EXIST_SLICE0_IN_CONF_FILE = "controller0"
EXIST_SLICE1_IN_CONF_FILE = "controller1"
NUM_FLOWSPACE_EXIST_SLICE0 = 6

SYSD_TYPE = 6
OUI_TYPE = 127


def spawnFlowVisor(parent, config_file=CONFIG_FILE, fv_cmd="flowvisor", fv_args=["-d","DEBUG"]):
    """
    Start a flowvisor with default or spcified config file
    Assumption: FlowVisor has already been installed
    @param parent parent must have logger (Logging object)
    @param config_file string specifying a configuration xml file.
           Mention only file name if it exists in the testing directory,
           otherwise specify it with full-path to the file.
           If not specified, a default xml file will be used.
    @param fv_cmd command to run. It is usually 'flowvisor'
    @param fv_args command line options when it runs flowvisor
    @return FlowVisor object on success, None if error
    """
    logprefix = "SpawnFlowVisor: "
    fv = None
    if not re.search("/",fv_cmd):
        if not (subprocess.Popen("which " + fv_cmd, shell=True, stdout=subprocess.PIPE).stdout.read()):
            parent.logger.error(logprefix + "Could not find " + fv_cmd)
            return fv
    cmdline = [fv_cmd] + fv_args + [CONFIG_FILE]
    parent.logger.info(logprefix + "Spawning '" +  " ".join(cmdline))
    fv=subprocess.Popen(cmdline,stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)

    if fv is not None:
        parent.logger.info(logprefix + "FlowVisor spawned at Pid=%d" % fv.pid)
    return fv


def tearDownFlowVisor(parent, fv=None):
    """
    Kill FlowVisor process
    @param parent parent must have FlowVisor object
    @return True
    """
    logprefix = "TearDownFlowVisor: "
    #parent.logger.info("-----------------Writing FV output-------------------")
    #for line in parent.fv.stdout:
    #    parent.logger.info(line)
    #parent.logger.info("-----------------Done FV output--------------------")
    parent.logger.info(logprefix + "Cleaning up FlowVisor (killing pid=%d)" %  parent.fv.pid)
    os.kill(parent.fv.pid,signal.SIGTERM)
    parent.logger.info(logprefix + "Sleeping for a second to let things die")
    time.sleep(1)
    parent.logger.info(logprefix + "Done cleaning up")
    if (fv != None):
        f = open('fv-error.out', 'w')
        output = fv.stdout.read()
        f.write(output)
        f.close()
    return True


def addSwitch(parent, num, port=OFPORT, switch_features=None, nPorts=4):
    """
    Start a fake switch and do handshake with FlowVisor and existing controllers
    @param parent parent must have logger (Logging object)
    @param num the number of this switch, starting at 0. Used for its name and dpid
    @param port TP port number the switch tries to connect. (Switch port on FlowVisor)
    @param switch_features ofp_features_reply instance
    @param nPorts the number of ports the switch has
    @return True if addSwitch was successful, False otherwise
    """
    logprefix = "AddSwitch: "
    name = "switch" + str(num)
    dpid = num
    timeout=parent.timeout
    try:
        sw = fakedevice.FakeSwitch(name, host='localhost', port=port)
    except:
        parent.logger.error(logprefix + "Failed to add switch: " + name)
        return False
    parent.switches.append(sw)

    # Handshake with FlowVisor
    parent.logger.info(logprefix + "Initial handshake with FV and controllers")
    send_msg = message.hello().pack()
    sw.send(send_msg)
    sw.start()

    try:
        m = sw.recv_blocking(timeout=timeout)
        exp = send_msg
        if (m != exp):
            parent.logger.error(logprefix + "Expecting: hello")
            parent.logger.error(logprefix + "Raw Response :   " + _b2a(m))
            parent.logger.error(logprefix + "Parsed Response: " + _pktParse(m))
            return False
        parent.logger.info(logprefix + "Got hello for " + name)

        m = sw.recv_blocking(timeout=timeout)
        exp = genFlowModFlush().pack()
        if (m != exp):
            parent.logger.error(logprefix + "Expecting: flow_mod with flush")
            parent.logger.error(logprefix + "Raw Response :   " + _b2a(m))
            parent.logger.error(logprefix + "Parsed Response: " + _pktParse(m))
            return False
        parent.logger.info(logprefix + "Got flow_mod flush for " + name)

        m = sw.recv_blocking(timeout=timeout)
        exp = message.features_request().pack()
        if (m != exp):
            parent.logger.error(logprefix + "Expecting: features_request")
            parent.logger.error(logprefix + "Raw Response :   " + _b2a(m))
            parent.logger.error(logprefix + "Parsed Response: " + _pktParse(m))
            return False
        parent.logger.info(logprefix + "Got features_request (from FV) for " + name)

        if switch_features == None:
            ports = []
            for dataport in range(nPorts):
                ports.append(dataport)
            switch_features = genFeaturesReply(ports=ports, dpid=dpid)
            switch_features.header.xid = parse.of_header_parse(m).xid
        send_msg = switch_features.pack()

        sw.send(send_msg)
        parent.logger.info(logprefix + "Sent switch_features to flowvisor")

        # Handshake with fake controller
        for cont in parent.controllers:
            parent.logger.info(logprefix + "Waiting for features_request from fakeController")
            m = sw.recv_blocking(timeout=timeout)

            ref_type = parse.of_header_parse(m).type
            ref_xid = parse.of_header_parse(m).xid

            if (ref_type != ofp.OFPT_FEATURES_REQUEST):
                parent.logger.error(logprefix + "Failed to get features_request from fake controller " + \
                        " for new switch " + name)
                return False
            parent.logger.info(logprefix + "Got features_request from fake controller for " + name)

            # Use the same switch_features as used for FlowVisor
            switch_features.header.xid = parse.of_header_parse(m).xid
            send_msg = switch_features.pack()
            sw.send(send_msg)
            parent.logger.info(logprefix + "Sent switch_features from " + name + " to fake controller")
    except (Exception),e :
        parent.logger.error(logprefix + "Failed: %s" %(str(e)))
        return False
    return True


def addController(parent, num):
    """
    Add a fake controller instance to be hooked by flowvisor
    @param parent parent must have logger (Logging object)
    @param num the number of this controller, starting at 0
    @return True if addController was successful, False otherwise
    """
    logprefix = "AddController: "
    timeout=parent.timeout
    name = "controller" + str(num)
    port = CTLPORT_OFFSET + num
    try:
        ctr = fakedevice.FakeController(
            name= name,
            port= port,
            timeout= timeout
            )
        ctr.start()
    except:
        parent.logger.error(logprefix + "Failed to add controller: " + name)
        return False
    parent.controllers.append(ctr)
    parent.logger.info(logprefix + "Connected with controller: " + ctr.name)
    return True


def tearDownFakeDevices(parent):
    """
    Check if parent has fake devices and tear them down
    @param parent parent must have list of controllers and switches
    @return True
    """
    logprefix = "TearDownFakeDevices: "
    for cont in parent.controllers:
        parent.logger.info(logprefix + "Cleaning up " + cont.name)
        cont.set_dead()
    for sw in parent.switches:
        parent.logger.info(logprefix + "Cleaning up " + sw.name)
        sw.set_dead()
    return True


def spawnApiClient(parent, user, pswd, rpcport = RPCPORT):
    """
    Spawn API client with specified account information
    @param parent parent must have logger (Logging object)
    @param user user name for connecting to FlowVisor API server
    @param pswd password for connecting to FlowVisor API server
    @param rpcport TP port on FlowVisor for API server
    @return ServerProxy object
    """
    # Connect from 'API server' and get some info
    logprefix = "SpawnApiClient: "
    url = "https://localhost:" + str(rpcport)
    passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
    passman.add_password(None, url, user, pswd)
    authhandler = urllib2.HTTPBasicAuthHandler(passman)
    opener = urllib2.build_opener(authhandler)
    parent.logger.info(logprefix + "Connecting to: " + url)
    return opener


def parseResponse(parent, data):
    j = json.loads(data)
    if 'error' in j:
        parent.logger.error("%s" % (j['error']['message']))
    return j['result']


def runCmd(parent, data, cmd, sv, rpcport = RPCPORT):
    j = { "id" : "fv-test", "method" : cmd, "jsonrpc" : "2.0" }
    h = {"Content-Type" : "application/json"}
    if data is not None:
        j['params'] = data
    url = "https://localhost:%d" % rpcport
    req = urllib2.Request(url, json.dumps(j), h)
    try:
        ph = sv.open(req)
        return parseResponse(parent,ph.read())
    except urllib2.HTTPError, e:
        if e.code == 401:
            parent.logger.error("Authentication failed: invalid password")
        elif e.code == 504:
            parent.logger.error("HTTP Error 504: Gateway timeout")
        else:
            print e
    except RuntimeError, e:
        print e

def setRule(parent, sv, rule, num_try=1, rpcport = RPCPORT):
    """
    Parses the command and additional parameters in the list, and send
    it to FlowVisor via API interface.
    Cmds are checked to have the right number of obliatory parameters. Optional
    ones are passed as an additional dict at the end of the rule list.
    @param parent parent must have logger (Logging object)
    @param sv ServerProxy object
    @param rule command to send to FlowVisor as a list
    [command, option1, option2, ....]
    where: command is a string specifying a command to send, option x is a string specifying an option for each command
    @param num_try Repetitive time it tries to send command
    @return False if error, True on success
    @return None if error or for API with no result, a value for API with result
    """
    logprefix = "SetRule: "
    success = False
    data = None
    while (True):
        try:
            if rule[0] == "list-slices":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "add-slice":
                if not (_ruleLenChecker(parent, rule, exp_len=6)):
                    return (success, data)
                s = {'slice-name' : rule[1], 'password' : rule[2],
                    'controller-url' : rule[3], 'admin-contact' : rule[4]}
                s.update(rule[5])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "update-slice":
                if not (_ruleLenChecker(parent, rule, exp_len=3)):
                    return (success, data)
                s = { 'slice-name' : rule[1] }
                s.update(rule[2])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "remove-slice":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'slice-name' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "update-slice-password":
                if not (_ruleLenChecker(parent, rule, exp_len=3)):
                    return (success, data)
                s = { 'slice-name' : rule[1], 'password' : rule[2] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-flowspace":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = {}
                s.update(rule[1])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "remove-flowspace":
                if not len(rule) > 0:
                    return (success, data)
                data = runCmd(parent, rule[1:], rule[0], sv)
            elif rule[0] == "add-flowspace":
                if not (_ruleLenChecker(parent, rule, exp_len=7)):
                    return (success, data)
                s = { 'name' : rule[1], 'dpid' : rule[2], 'priority' : rule[3],
                    'match' : rule[4], 'slice-action' : rule[5] }
                s.update(rule[6])
                data = runCmd(parent, [s], rule[0], sv)
                time.sleep(0.5)
            elif rule[0] == "update-flowspace":
                if not (_ruleLenChecker(parent, rule, exp_len=3)):
                    return (success, data)
                s = { 'name' : rule[1] }
                s.update(rule[2])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-version":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "set-config":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = {}
                s.update(rule[1])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "get-config":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = {}
                s.update(rule[1])
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "save-config":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "list-slice-info":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'slice-name' : rule[1]}
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-datapaths":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "list-links":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "list-datapath-info":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'dpid' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-slice-stats":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'slice-name' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-datapath-stats":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'dpid' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-fv-health":
                if not (_ruleLenChecker(parent, rule, exp_len=1)):
                    return (success, data)
                data = runCmd(parent, None, rule[0], sv)
            elif rule[0] == "list-slice-health":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = { 'slice-name' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "register-event-callback":
                if not (_ruleLenChecker(parent, rule, exp_len=5)):
                    return (success, data)
                s = { 'url' : rule[1], 'method' : rule[2], 'event-type' : rule[3],
                    'cookie' : rule[4] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "unregister-event-callback":
                if not (_ruleLenChecker(parent, rule, exp_len=4)):
                    return (success, data)
                s = {'method' : rule[1], 'event-type' : rule[2],
                    'cookie' : rule[3] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-datapath-flowdb":
                if not (_ruleLenChecker(parent, rule, exp_len=2)):
                    return (success, data)
                s = {'dpid' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            elif rule[0] == "list-datapath-flowrewritedb":
                if not (_ruleLenChecker(parent, rule, exp_len=3)):
                    return (success, data)
                s = {'dpid' : rule[2], 'slice-name' : rule[1] }
                data = runCmd(parent, s, rule[0], sv)
            else:
                parent.logger.error(logprefix + "Illegal Command: " + rule[0])
                return (success, data)
            success = True
            return (success, data)

        except (Exception),e :
            if num_try <= 1:
                parent.logger.error(logprefix + "Failed: %s" %(str(e)))
                return (success, data)
            else:
                num_try = num_try - 1
                parent.logger.debug(logprefix + "Could not connect to FV. Next attempt: 0.5s later. %d attempts remain" %(num_try))
                time.sleep(0.5)


def _ruleLenChecker(parent, rule, exp_len):
    """
    Check the length of the given rule. If not expected, return False, otherwise True
    @param parent parent must have logger (Logging object)
    @param rule command to send to FlowVisor as a list
    [command, option1, option2, ....]
    where: command is a string specifying a command to send, option x is a string specifying an option for each command
    @param exp_len Expected numbers of options including the command itself
    @return False if error, True on success
    """
    logprefix = "RuleLenChecker: "
    if (len(rule) != exp_len):
        parent.logger.error(logprefix + "The number of options for %s must be %d" % (rule[0], (exp_len-1)))
        return False
    return True


def chkFlowdb(parent, controller_number, switch_number, exp_count, exp_rewrites=-1):
    """
    Query FlowVisor with getSwitchFlowDB and getSliceRewriteDB,
    and check the number of flows. Compare each value with the given
    exp_num value and return the comparison result.
    @param parent parent must have ServerProxy object (sv), controllers, switches and logger
    @param controller_number integer describing that it is the x th controller.
    Used for tcp port number and slice name
    @param switch_number integer describing that it is the x th switch. Used for DPID.
    @param exp_count The number of flow spaces it should have
    @return False if fail, True on success
    """
    if exp_rewrites == -1:
        exp_rewrites = exp_count
    logprefix = "ChkFlowDB: "
    slicename = parent.controllers[controller_number].name
    dpid_str = str(switch_number)

    (success, flows) = setRule(parent, parent.sv, ["list-datapath-flowdb", dpid_str])
    if success:
        parent.logger.info("flows are:")
        parent.logger.info(flows)
        num_flows = len(flows)
        parent.logger.info(logprefix + "SwitchFlowDB: Got %d flows" % num_flows)
    else:
        parent.logger.error(logprefix + "SwitchFlowDB: Could not get response")
        return False
    parent.logger.info(logprefix + "SwitchFlowDB Info:")
    for flow in flows:
        for key,val in flow.iteritems():
            parent.logger.info("     %s=%s" % (key,val))
    if num_flows != exp_count:
        parent.logger.error(logprefix + "Expected: %d flows, got: %d flows" % (exp_count, num_flows))
        return False

    (success, rewrites) = setRule(parent, parent.sv, ["list-datapath-flowrewritedb", slicename, dpid_str])
    if success:
        num_rewrites = len(rewrites)
        parent.logger.info(logprefix + "SliceRewriteDB: Got %d rewrites" % num_rewrites)
    else:
        parent.logger.error(logprefix + "SliceRewriteDB: Could not get response")
        return False
    parent.logger.info(logprefix + "SliceRewriteDB Info:")
    for flow, rewrites in rewrites.iteritems():
        for rewrite in rewrites:
            for key,val in rewrite.iteritems():
                parent.logger.info("     => %s=%s" % (key,val))
    if num_rewrites != exp_rewrites:
        parent.logger.error(logprefix + "Expected: %d rewrites, got: %d rewrites" % (exp_count, num_rewrites))
        return False

    return True


def chkSwitchStats(parent, switch_number, ofproto, exp_snd_count, exp_rcv_count):
    """
    Query FlowVisor with getSwitchStats and check the number of messages sent/received.
    Compare the values with the given exp_snd_count and exp_rcv_count values,
    then return the comparison result.
    @param parent parent must have ServerProxy object and logger
    @param switch_number integer describing that it is the x th switch, starting at 0. Used for DPID.
    @param ofproto string specifying which OF protocol message to be verified
    @param exp_snd_count The number of messages it should have sent. Give -1 to indicate Don'tCare. (Not used for now)
    @param exp_rcv_count The number of messages it should have received. Give -1 to indicate Don'tCare. (Not used for now)
    @return False if fail, True on success
    """
    logprefix = "ChkSwStats: "
    swname = parent.switches[switch_number].name
    dpid_str = str(switch_number)
    (success, stats) = setRule(parent, parent.sv, ["list-datapath-stats", dpid_str])
    if success:
        parent.logger.info(logprefix + "Info for " + swname + ":")
        parent.logger.info(stats)
        return True
    else:
        parent.logger.error(logprefix + "Could not get response")
        return False
    #@TODO How can I verify the results?


def chkSliceStats(parent, controller_number, ofproto, exp_snd_count, exp_rcv_count):
    """
    Query FlowVisor with getSliceStats and check the number of messages sent/received.
    Compare the values with the given exp_snd_count and exp_rcv_count values,
    then return the comparison result.
    @param parent parent must have ServerProxy object and logger
    @param controller_number integer describing that it is the x th controller, starting at 0.
           Used for tcp port number and slice name
    @param ofproto string specifying which OF protocol message to be verified
    @param exp_snd_count The number of messages it should have sent. Give -1 to indicate Don'tCare. (Not used for now)
    @param exp_rcv_count The number of messages it should have received. Give -1 to indicate Don'tCare. (Not used for now)
    @return False if fail, True on success
    """
    logprefix = "ChkSliceStats: "
    slicename = parent.controllers[controller_number].name
    (success, stats) = setRule(parent, parent.sv, ["list-slice-stats", slicename])
    if success:
        parent.logger.info(logprefix + "Info for " + slicename + ":")
        parent.logger.info(stats)
        return True
    else:
        parent.logger.error(logprefix + "Could not get response")
        return False
    #@TODO How can I verify the results?


def setUpTestEnv(parent, config_file=CONFIG_FILE, fv_cmd="flowvisor", num_of_switches=1, num_of_controllers=2, rules=None):
    """
    Do: spawnFlowVisor, setRule, addController and addSwitch.
    @param parent parent must have logger (Logging object)
    @param config_file string specifying a configuration xml file.
           Mention only file name if it exists in the testing directory,
           otherwise specify it with full-path to the file.
           If not specified, a default xml file will be used.
    @param num_of_switches number of switches to be added (starting at 1)
    @param num_of_controllers number of controllers to be added (starting at 1)
    @param rules list of commands to send to FlowVisor
    @return FlowVisor object on success, None if error
    @return ServerProxy object on success, None if error
    @return sv_ret True if rule has been set successfully, otherwise False
    @return ctl_ret True if rule has been set successfully, otherwise False
    @return sw_ret True if rule has been set successfully, otherwise False
    """
    logprefix = "SetUpTestEnv: "
    user="fvadmin"
    pswd="0fw0rk"
    rpcport=RPCPORT

    fv = None
    sv = None
    sv_ret = False
    ctl_ret = False
    sw_ret = False

    fv = spawnFlowVisor(parent, fv_cmd=fv_cmd, config_file=config_file)
    if fv == None:
        parent.logger.error(logprefix + "Failed spawning FlowVisor")
        return (fv, sv, sv_ret, ctl_ret, sw_ret)

    sv = spawnApiClient(parent, user, pswd, rpcport)

    # First access to FV. Wait for FV to start. Wait 20times(10s) max.
    (success, data) = setRule(parent, sv, ["list-slices"], num_try=20)
    if (success == False):
        parent.logger.error(logprefix + "list-slices: Could not get response")
        return (fv, sv, sv_ret, ctl_ret, sw_ret)

    parent.logger.info(logprefix + "SliceList: " + str(data))
    for slic in data:
        (success, sliceinfo) = setRule(parent, sv, ["list-slice-info", slic['slice-name']])
        parent.logger.info(logprefix + "SliceInfo: " + str(sliceinfo))

    if rules != None:
        for rule in rules:
            (sv_ret, data) = setRule(parent, sv, rule)
            if (sv_ret == False):
                parent.logger.error(logprefix + "Failed setting rule")
                return (fv, sv, sv_ret, ctl_ret, sw_ret)
            parent.logger.info(logprefix + "Set additional rule: " + str(data))
    else:
        sv_ret = True

    if num_of_controllers > 0:
        for num_ctl in range(num_of_controllers):
            ctl_ret = addController(parent, num_ctl)
            if ctl_ret == False:
                parent.logger.error(logprefix + "Failed adding contollers")
                return (fv, sv, sv_ret, ctl_ret, sw_ret)
    else:
        ctl_ret = True

    if num_of_switches > 0:
        for num_sw in range(num_of_switches):
            sw_ret = addSwitch(parent, num_sw)
            if sw_ret == False:
                parent.logger.error(logprefix + "Failed adding switches")
                return (fv, sv, sv_ret, ctl_ret, sw_ret)
    else:
        sw_ret = True

    return (fv, sv, sv_ret, ctl_ret, sw_ret)

def recvStats(parent, swId, typ):
    sw = parent.switches[swId]
    pkt = sw.recv_blocking(timeout = 5)
    if pkt is None:
        return (-1,False)

    offset = 0
    hdr = parse.of_header_parse(pkt[offset:])
    if not hdr:
        res = "Could not parse OpenFlow header, pkt len: " + len(pkt)
        return (-1,res)
    if hdr.length == 0:
        res = "Header length is zero"
        return (-1,res)

    # Extract the raw message bytes
    rawmsg = pkt[offset : offset + hdr.length]
    msg = parse.of_message_parse(rawmsg)
    if not msg:
        res = "Could not parse message"
        return (-1, res)
    if isinstance(msg, typ):
        return (msg.header.xid, True)
    elif isinstance(msg, message.echo_request):
        return recvStats(parent, 0, typ)
    else:
        print "received %s" % msg
        return (-1,False)


def ofmsgSndCmp(parent, snd_list, exp_list, xid_ignore=False, hdr_only=False, ignore_cookie=True, cookies=[]):
    """
    Wrapper method for comparing received message and expected message
    See ofmsgSndCmpWithXid()
    """
    (success, ret_xid) = ofmsgSndCmpWithXid(parent, snd_list, exp_list, xid_ignore, hdr_only, ignore_cookie, cookies)
    return success


def ofmsgSndCmpWithXid(parent, snd_list, exp_list, xid_ignore=False, hdr_only=False, ignore_cookie=True, cookies=[]):
    """
    Extract snd_list (list) and exp_list (list of list).
    With snd_list, send a message from the specific switch/controller ports.
    Then using the information inside exp_list, check the specified switch/controller to
    wait for message(s).
    Compare the received data with expected data.
    It accept multiple expected messages on multiple switches/controllers.
    It also supports to check if any packet was not received on specified
    switches/controllers.
    @param parent parent must have FlowVisor object for the test and logger
    @param snd_list list of the information for sending a message.
    ["controller", num, sw_num, buf] or ["switch", num, buf]
    num is switch number or controller number (starting at 0) as int,
    sw_num is switch number (starting at 0) if sw_ctl is "controller".
    buf is OpenFlow message created using the test utilities
    @param exp_list list of list of the information about expected messages
    [[sw_ctrl, num, buf], [sw_ctrl, num, buf], ---- [sw_ctrl, num, buf]]
    where: sw_ctrl is a string, either "switch" or "controller",
    num is switch number or controller number (starting at 0) as int,
    buf is OpenFlow message created using the test utilities.
    If messages should not be received, this field must be None.
    @param xid_ignore If True, it doesn't care about xid difference
    @param hdr_only If True, it only checks OpenFlow header
    @return False if error, True on success
    @return xid in received message. If not successful, returns 0
    """
    logprefix = "MsgSndCmp: "
    timeout=parent.timeout
    snd_sw_ctrl = snd_list[0]
    snd_num = snd_list[1]
    ret_xid = 0

    if snd_sw_ctrl == "switch":
        snd_msg = snd_list[2].pack()
        try:
            sw = parent.switches[snd_num]
        except (KeyError):
            parent.logger.error(logprefix + "Unknown switch " + str(snd_num))
            return (False, ret_xid)
        parent.logger.info(logprefix + "Sending message from " + sw.name)
        sw.send(snd_msg)
    elif snd_sw_ctrl == "controller":
        sw_num = snd_list[2]
        snd_msg = snd_list[3].pack()
        try:
            cont = parent.controllers[snd_num]
        except (KeyError):
            parent.logger.error(logprefix + "Unknown controller " + str(snd_num))
            return (False, ret_xid)
        try:
            sw = cont.getSwitch(sw_num)
        except (KeyError):
            parent.logger.error(logprefix + "Unknown switch " + str(sw_num) + " connected to " + cont.name)
            return (False, ret_xid)
        parent.logger.info(logprefix + "Sending message from " + cont.name + " to " + sw.name)
        sw.send(snd_msg)
    else:
        parent.logger.error(logprefix + "Originated device not specified in snd_list")
        return (False, ret_xid)

    for exp in exp_list:
        exp_sw_ctrl = exp[0]
        exp_num = exp[1]
        if exp[2]:
            exp_msg = exp[2].pack()
        else:
            exp_msg = None
        if exp_sw_ctrl == "switch":
            try:
                sw = parent.switches[exp_num]
            except (KeyError):
                parent.logger.error(logprefix + "Unknown switch " + str(exp_num))
                return (False, ret_xid)
            if exp_msg:
                response = sw.recv_blocking(timeout=timeout)
                if response:
                    ret_xid = int(_b2a(response[4:8]), 16)
                    if xid_ignore:
                        response = response[0:4] + exp_msg[4:8] + response[8:]
                if hdr_only:
                    if response[0:8] != exp_msg[0:8]:
                        parent.logger.error(logprefix + "Parsed Expecting: " + _hdrParse(exp_msg))
                        parent.logger.error(logprefix + "Parsed Response:  " + _hdrParse(response))
                        #@TODO Check some stats
                        parent.logger.error(logprefix + sw.name + ": Received unexpected message")
                        return (False, ret_xid)
                else:
                    if ignore_cookie:
                        resp = parse.of_message_parse(response)
                        exp_m = parse.of_message_parse(exp_msg)
                        if (isinstance(resp,message.flow_mod)
                                or isinstance(resp, message.flow_removed)):
                            resp.ignore_cookie = True
                            cookies.append(resp.cookie)
                    else:
                        resp = response
                        exp_m = exp_msg
                    if resp != exp_m:
                        parent.logger.error(logprefix + "Raw Expecting: " + _b2a(exp_msg))
                        parent.logger.error(logprefix + "Raw Response:  " + _b2a(response))
                        parent.logger.error(logprefix + "Parsed Expecting: " + _pktParse(exp_msg))
                        parent.logger.error(logprefix + "Parsed Response:  " + _pktParse(response))
                        #@TODO Check some stats
                        parent.logger.error(logprefix + sw.name + ": Received unexpected message")
                        return (False, ret_xid)
            else:
                response = sw.recv()
                if response != None:
                    parent.logger.error(logprefix + "Message not expected")
                    parent.logger.error(logprefix + "Raw Received:    " + _b2a(response))
                    parent.logger.error(logprefix + "Parsed Received: " + _pktParse(response))
                    return (False, ret_xid)

        elif exp_sw_ctrl == "controller":
            try:
                cont = parent.controllers[exp_num]
            except (KeyError):
                parent.logger.error(logprefix + "Unknown controller " + str(exp_num))
                return (False, ret_xid)
            try:
                if snd_sw_ctrl == "controller":
                    sw = cont.getSwitch(sw_num)
                else:
                    sw = cont.getSwitch(snd_num)
            except (KeyError):
                parent.logger.error(logprefix + "Unknown switch " + str(snd_num) + " connected to " + cont.name)
                return (False, ret_xid)
            if exp_msg:
                response = sw.recv_blocking(timeout=timeout)
                if response:
                    ret_xid = int(_b2a(response[4:8]), 16)
                    if xid_ignore:
                        response = response[0:4] + exp_msg[4:8] + response[8:]
                if hdr_only:
                    if response is not None and response[0:8] != exp_msg[0:8]:
                        parent.logger.error(logprefix + "Parsed Expecting: " + _hdrParse(exp_msg))
                        parent.logger.error(logprefix + "Parsed Response:  " + _hdrParse(response))
                        #@TODO Check some stats
                        parent.logger.error(logprefix + sw.name + ": Received unexpected message")
                        return (False, ret_xid)
                    elif response is None and exp_msg is not None:
                        return (False, ret_xid)
                else:
                    if response != exp_msg:
                        parent.logger.error(logprefix + "Raw Expecting: " + _b2a(exp_msg))
                        parent.logger.error(logprefix + "Raw Response:  " + _b2a(response))
                        parent.logger.error(logprefix + "Parsed Expecting: " + _pktParse(exp_msg))
                        parent.logger.error(logprefix + "Parsed Response:  " + _pktParse(response))
                        #@TODO Check some stats
                        parent.logger.error(logprefix + parent.controllers[exp_num].name + ": Received unexpected message")
                        return (False, ret_xid)
            else:
                response = sw.recv()
                if response != None:
                    parent.logger.error(logprefix + "Message not expected")
                    parent.logger.error(logprefix + "Raw Received:    " + _b2a(response))
                    parent.logger.error(logprefix + "Parsed Received: " + _pktParse(response))
                    return (False, ret_xid)

        else:
            parent.logger.error(logprefix + "Target not specified in one of exp_list")
            return (False, ret_xid)

    return (True, ret_xid)


def simplePacket(pktlen=100,
                 dl_dst='00:01:02:03:04:05',
                 dl_src='00:06:07:08:09:0a',
                 dl_vlan=0xffff,
                 dl_vlan_pcp=0,
                 dl_vlan_cfi=0,
                 dl_type = ETHERTYPE_IP,
                 nw_src='192.168.0.1',
                 nw_dst='192.168.0.2',
                 nw_tos=0,
                 nw_proto=socket.IPPROTO_TCP,
                 tp_src=1234,
                 tp_dst=80
                 ):
    """
    Return a simple packet
    Users shouldn't assume anything about this packet other than that
    it is a valid ethernet/IP/TCP frame.
    It generates a packet in a shape of TCP, UDP, ICMP, ARP, IP,
    Raw ethernet, with or without a VLAN tag.
    If dl_type is other than IP or ARP, the upper layer parameters will be ignored
    If nw_proto is other than TCP, UDP or ICMP, the upper layer parameters will be ignored
    Supports a few parameters
    @param pktlen Length of packet in bytes w/o CRC
    @param dl_dst Destination MAC
    @param dl_src Source MAC
    @param dl_vlan VLAN ID, No VLAN tags if the value is 0xffff
    @param dl_vlan_pcp VLAN priority. Valid only dl_vlan is in a valid range
    @param dl_vlan_cfi VLAN CFI
    @param dl_type Type of L3
    @param nw_src IP source
    @param nw_dst IP destination
    @param nw_tos IP ToS
    @param nw_proto L4 protocol When ARP is specified in dl_type, it is used for op code
    @param tp_dst UDP/TCP destination port
    @param tp_src UDP/TCP source port
    @return valid packet
    """
    # Note Dot1Q.id is really CFI
    if (dl_vlan == 0xffff):
        pkt = scapy.Ether(dst=dl_dst, src=dl_src)
    else:
        dl_vlan = dl_vlan & 0x0fff
        pkt = scapy.Ether(dst=dl_dst, src=dl_src)/ \
            scapy.Dot1Q(prio=dl_vlan_pcp, id=dl_vlan_cfi, vlan=dl_vlan)

    if (dl_type == ETHERTYPE_IP):
        pkt = pkt/ scapy.IP(src=nw_src, dst=nw_dst, tos=nw_tos)
        if (nw_proto == socket.IPPROTO_TCP):
            pkt = pkt/ scapy.TCP(sport=tp_src, dport=tp_dst)
        elif (nw_proto == socket.IPPROTO_UDP):
            pkt = pkt/ scapy.UDP(sport=tp_src, dport=tp_dst)
        elif (nw_proto == socket.IPPROTO_ICMP):
            pkt = pkt/ scapy.ICMP(type=tp_src, code=tp_dst)

    elif (dl_type == ETHERTYPE_ARP):
        pkt = pkt/ scapy.ARP(op=nw_proto, hwsrc=dl_src, psrc=nw_src, hwdst=dl_dst, pdst=nw_dst)
        return pkt

    pkt = pkt/("D" * (pktlen - len(pkt)))
    return pkt

"""
def simpleLldpPacket(dl_dst='01:80:c2:00:00:0e',
                     dl_src='00:06:07:08:09:0a',
                     dl_type=ETHERTYPE_LLDP,
                     lldp_chassis_id="04e2b8dc3b1795",
                     lldp_port_id="020001",
                     lldp_ttl="0078",
                     trailer=None
                     ):
    Return a simple LLDP packet
    Users shouldn't assume anything about this packet other than that
    it is a valid LLDP packet
    It generates a packet with or without FlowVisor specific trailer.
    Supports a few parameters
    @param dl_dst Destination MAC
    @param dl_src Source MAC
    @param dl_type The value will simply put in the packet. Don't touch if you want valied LLDP packet
    @param lldp_chassis_id chassis id to be used in LLDP packet
    @param lldp_port_id port id to be used in LLDP packet
    @param lldp_ttl ttl to be used in LLDP packet
    @param trailer string to be attatched on LLDP. Use genTrailer function to create a valid trailer
    @return LLDP packet
    chassisid_tlv = _tlvPack(CHASSISID_TYPE, lldp_chassis_id)
    portid_tlv = _tlvPack(PORTID_TYPE, lldp_port_id)
    ttl_tlv = _tlvPack(TTL_TYPE, lldp_ttl)
    eol_tlv = struct.pack("!H", 0x0000)
    payload = chassisid_tlv + portid_tlv + ttl_tlv + eol_tlv

    ether = scapy.Ether(src=dl_src, dst=dl_dst, type=dl_type)
    if trailer:
        pkt = str(ether) + payload + trailer
    else:
        pkt = str(ether) + payload
    return pkt"""

def simpleLldpPacket(dl_dst='01:80:c2:00:00:0e',
                     dl_src='00:06:07:08:09:0a',
                     dl_type=ETHERTYPE_LLDP,
                     lldp_chassis_id="04e2b8dc3b1795",
                     lldp_port_id="020001",
                     lldp_ttl="0078",
                     lldp_oui_id=None
                     ):
    """
    Return a simple LLDP packet
    Users shouldn't assume anything about this packet other than that
    it is a valid LLDP packet
    It generates a packet with or without FlowVisor specific trailer.
    Supports a few parameters
    @param dl_dst Destination MAC
    @param dl_src Source MAC
    @param dl_type The value will simply put in the packet. Don't touch if you want valied LLDP packet
    @param lldp_chassis_id chassis id to be used in LLDP packet
    @param lldp_port_id port id to be used in LLDP packet
    @param lldp_ttl ttl to be used in LLDP packet
    @param trailer string to be attatched on LLDP. Use genTrailer function to create a valid trailer
    @return LLDP packet
    """
    payload = None
    if(lldp_chassis_id != None):
        chassisid_tlv = _tlvPack(CHASSISID_TYPE, lldp_chassis_id)
        #print("chassisid_tlv: ",chassisid_tlv)
    if(lldp_port_id != None):
        portid_tlv = _tlvPack(PORTID_TYPE, lldp_port_id)
        #print("portid_tlv: ",portid_tlv)
    if(lldp_ttl != None):
        ttl_tlv = _tlvPack(TTL_TYPE, lldp_ttl)
        #print("ttl_tlv: ",ttl_tlv)
    if(lldp_oui_id != None):
        #oui_info_tlv = genOUIString("magic flowvisor1","controller0")
        #print("oui_info_tlv: ",oui_info_tlv)
        #oui_string = lldp_oui_id + oui_info_tlv
        oui_string = "controller00magic flowvisor10"
        oui_tlv = _tlvPack(OUI_TYPE, lldp_oui_id, oui_string)
        oui_str = genOUIString("magic flowvisor1", lldp_oui_id, "controller0")
        print("oui_tlv: ",oui_tlv)
        print("oui_str: ",oui_str)
    #if(lldp_chassis_id != None and lldp_port_id != None and lldp_ttl != None and lldp_oui_id != None):
        eol_tlv = struct.pack("!H", 0x0000)
        #payload = chassisid_tlv + portid_tlv + ttl_tlv + oui_tlv + oui_str + eol_tlv
        payload = oui_tlv + oui_str + eol_tlv
        print("payload: ",payload)
    ether = scapy.Ether(src=dl_src, dst=dl_dst, type=dl_type)
    if (payload!= None):
        pkt = str(ether) + payload
    else:
        pkt = str(ether)
    return pkt

def genOUIString(flowvisor_name, ouiId = "a4230501", controller_name = None):
    """
    Generate a FlowVisor specific LLDP trailer
    FlowVisor adds a trailer right after a valid sets of tlv.
    The trailer is structured as follows:
    -2bytes of TL (7bits of type and 9 bits of length. The type is 'chassis id'; = 1)
    -1byte of chassis id
    -At least 10bytes of 'slice name' ascii, followed by null stop
     (Padded if the string is less than 10bytes)
    -At least 20bytes of flowvisor name' ascii, followed by null stop
     (Padded if the string is less than 20bytes)
    -1byte of length-of-slice name (with padding + null)
    -1byte of length-of-flowvisor name (with padding + null)
    -4bytes of magic word (de ad ca fe)
    @param controller_name controller name used in a trailer
    @param flowvisor_name FlowVisor name used in a trailer. Have to be more than or equal to 20bytes
    @return trailer as a string used between FlowVisor-switch LLDP exchange
    """
    if(controller_name != None):
        len_ctl = len(controller_name)+1 # for null stop
        ctl_name_lst = map(ord, list(controller_name))
        #ctl_name_lst.append(0)
    len_fv = len(flowvisor_name)+1 # for null stop
    fv_name_lst = map(ord, list(flowvisor_name))
    #fv_name_lst.append(0)
    #oui_lst = map(ord,list(ouiId))

    val_lst = []
    if(controller_name != None):
        #val_lst += oui_lst
        val_lst += ctl_name_lst
        val_lst += [0]
        val_lst += fv_name_lst
        val_lst += [0]
        val_lst += [len_ctl]
        val_lst += [len_fv]
    else:
        #val_lst += oui_lst
        val_lst += fv_name_lst
        val_lst += [0]
        val_lst += [len_fv]
    #print("val_lst: ",val_lst)
    trailer = None
    for i in val_lst:
        if trailer:
            trailer = trailer + struct.pack("!B", i)
        else:
            trailer = struct.pack("!B", i)
    #trailer = _b2a(trailer)
    return trailer
    #return _tlvPack(127, trailer)




"""
def genTrailer(controller_name, flowvisor_name):"""
"""
    Generate a FlowVisor specific LLDP trailer
    FlowVisor adds a trailer right after a valid sets of tlv.
    The trailer is structured as follows:
    -2bytes of TL (7bits of type and 9 bits of length. The type is 'chassis id'; = 1)
    -1byte of chassis id
    -At least 10bytes of 'slice name' ascii, followed by null stop
     (Padded if the string is less than 10bytes)
    -At least 20bytes of flowvisor name' ascii, followed by null stop
     (Padded if the string is less than 20bytes)
    -1byte of length-of-slice name (with padding + null)
    -1byte of length-of-flowvisor name (with padding + null)
    -4bytes of magic word (de ad ca fe)
    @param controller_name controller name used in a trailer
    @param flowvisor_name FlowVisor name used in a trailer. Have to be more than or equal to 20bytes
    @return trailer as a string used between FlowVisor-switch LLDP exchange
"""
"""
    CHASSIS_ID = 7
    MAGIC = [0xde,0xad,0xca,0xfe]
    len_ctl = len(controller_name)+1 # for null stop
    len_fv = len(flowvisor_name)+1 # for null stop

    ctl_name_lst = map(ord, list(controller_name))
    ctl_name_lst.append(0)
    fv_name_lst = map(ord, list(flowvisor_name))
    fv_name_lst.append(0)

    val_lst = []
    val_lst.append(CHASSIS_ID)
    val_lst = val_lst + ctl_name_lst + fv_name_lst
    val_lst.append(len_ctl)
    val_lst.append(len_fv)
    val_lst = val_lst + MAGIC
    trailer = None
    for i in val_lst:
        if trailer:
            trailer = trailer + struct.pack("!B", i)
        else:
            trailer = struct.pack("!B", i)

    return _tlvPack(1, _b2a(trailer))
"""

def _tlvPack(tlv_type, tlv_value, oui_info_string=None):
    """
    Generate a set of tlv to be used in LLDP packet
    @param tlv_type tlv_type
    @param tlv_value tlv_value
    @return a pack of tlv
    """
    tl_len = 2 #2bytes
    tlv_type_sft = (tlv_type << 9)
    #tlv_len = (len(tlv_value))/2 + tl_len
    if tlv_type != OUI_TYPE:
        tlv_len = len(tlv_value)/2
    elif(tlv_type == OUI_TYPE and oui_info_string != None):
        tlv_len = len(tlv_value)/2 + len(oui_info_string) + 2 #2 for null char
    #print("tlv_len: ",tlv_len)
    pack_tl = struct.pack("!H", (tlv_type_sft + tlv_len))
    #print(pack_tl + _a2b(tlv_value))
    #_a2b()  =  binascii.unhexlify(str)
    #if tlv_type != OUI_TYPE:
    return (pack_tl + _a2b(tlv_value))
    #else:
    #    return(pack_tl)

def genFloModFromPkt(parent, pkt, ing_port=ofp.OFPP_NONE, action_list=None, wildcards=0,
                     egr_port=None):
    """
    Create a flow_mod message from a packet
    The created flow_mod will match on the given packet with given wildcards.
    @param parent parent must have logger (Logging object)
    @param pkt Parsed and used to construct a flow_mod
    @param ing_port ingress port
    @param action_list list of actions
    @param wildcards Used as a field on match structure
    @param egr_port Used for output action
    @return flow_mod
    """
    logprefix = "FlowMsgCreate: "
    match = parse.packet_to_flow_match(pkt)
    parent.assertTrue(match is not None, "Flow match from pkt failed")
    match.wildcards = wildcards
    match.in_port = ing_port

    request = message.flow_mod()
    request.match = match
    request.buffer_id = 0xffffffff

    if action_list is not None:
        for act in action_list:
            parent.logger.debug(logprefix + "Adding action " + act.show())
            rv = request.actions.add(act)
            parent.assertTrue(rv, "Could not add action" + act.show())

    # Set up output/enqueue action if directed
    if egr_port is not None:
        act = action.action_output()
        act.port = egr_port
        rv = request.actions.add(act)
        parent.assertTrue(rv, "Could not add output action " + str(egr_port))

    parent.logger.debug(logprefix + str(request.show()))

    return request


def genPacketIn(xid=None,
                buffer_id=None,
                in_port=3,
                pkt=simplePacket()):
    """
    Create a packet_in message with genericly usable values
    @param xid transaction ID used in OpenFlow header
    @param buffer_id bufer_id
    @param in_port ingress port
    @param pkt a packet to be attached on packet_in
    @return packet_in
    """
    if xid == None:
        xid = genVal32bit()
    if buffer_id == None:
        buffer_id = genVal32bit()

    packet_in = message.packet_in()
    packet_in.header.xid = xid
    packet_in.buffer_id = buffer_id
    packet_in.in_port = in_port
    packet_in.reason = ofp.OFPR_NO_MATCH
    if pkt is not None:
        packet_in.data = str(pkt)
    return packet_in


def genPacketOut(parent,
                 xid=None,
                 buffer_id=None,
                 in_port=ofp.OFPP_NONE,
                 action_ports=[],
                 pkt=simplePacket()):
    """
    Create a packet_out message with genericly usable values
    @param parent parent must have logger (Logging object)
    @param xid transaction ID used in OpenFlow header
    @param buffer_id bufer_id
    @param in_port ingress port
    @param action_ports a list of output ports
    @param pkt a packet to be attached on packet_out
    @return packet_out
    """
    if xid == None:
        xid = genVal32bit()
    if buffer_id == None:
        buffer_id = 0xffffffff

    packet_out = message.packet_out()
    packet_out.header.xid = xid
    packet_out.buffer_id = buffer_id
    packet_out.in_port = in_port

    for action_port in action_ports:
        act = action.action_output()
        act.port = action_port
        act.max_len = 0x80#Changes this from 0x80 to 0xc8
        parent.assertTrue(packet_out.actions.add(act), 'Could not add action to msg')
    if pkt is not None:
        packet_out.data = str(pkt)
    return packet_out


def genFlowModFlush():
    """
    Genericly usable flush_flow command
    @return flow_mod with delete command
    """
    flow_mod = message.flow_mod()
    flow_mod.match.wildcards = ofp.OFPFW_ALL
    flow_mod.command = ofp.OFPFC_DELETE
    flow_mod.priority = 0
    flow_mod.buffer_id = 0xffffffff
    flow_mod.out_port = ofp.OFPP_NONE
    return flow_mod


def genFeaturesReply(dpid, ports = [0,1,2,3], xid=1):
    """
    Features Reply with some specific parameters.
    For HW address of each port, it exploits dpid and the port number
    @param dpid dpid in 32bit int
    @param ports a list of the ports this switch has
    @param xid transaction ID
    @return features_reply
    """
    feat_reply = message.features_reply()
    feat_reply.header.xid = xid
    feat_reply.datapath_id = dpid
    feat_reply.n_buffers = 128
    feat_reply.n_tables = 2
    feat_reply.capabilities = (ofp.OFPC_FLOW_STATS + ofp.OFPC_TABLE_STATS + ofp.OFPC_PORT_STATS)
    feat_reply.actions = ofp.OFPAT_OUTPUT
    for i in ports:
        name = "port " + str(i)
        byte4 = (dpid & 0xff0000)>>16
        byte3 = (dpid & 0xff00)>>8
        byte2 = dpid & 0xff
        byte1 = (i & 0xff00)>>8
        byte0 = i & 0xff
        addr = [0, byte4, byte3, byte2, byte1, byte0]
        feat_reply.ports.append(genPhyPort(name, addr, port_no=i))
    return feat_reply


def genPhyPort(name, addr, port_no):
    """
    Genericly usable phy_port
    @param name The port's name in string
    @param addr hw_addr (MAC address) as array: [xx,xx,xx,xx,xx,xx]
    @param port_no port number
    @return phy_port
    """
    phy_port = ofp.ofp_phy_port()
    phy_port.port_no = port_no
    phy_port.hw_addr = addr
    phy_port.name = name
    return phy_port


def genVal32bit():
    """
    Generate random 32bit value used for xid, dpid and buffer_id
    @return 32bit value excluding 0 and 0xffffffff
    """
    return random.randrange(1,0xfffffffe)


def _a2b(str):
    """
    Translate almost human readible form with whitespace to a binary form
    @param str a set of ascii values of 0 to F
    @return binary hexadecimal value
    """
    return binascii.unhexlify(str)


def _b2a(str):
    """
    Translate binary to an ascii hex code (almost) human readable form
    @parem binary hexadecimal value
    @return a set of ascii values of 0 to F
    """
    if str :
        return binascii.hexlify(str)
    else :
        return "***NONE***"


def _hdrParse(pkt):
    """
    OpenFlow header parser used for logging
    @param pkt a packed packet. If it is an OpenFlow message, used for parsing
    @return parsed information as a string, error message if parsing failed
    """
    if pkt is None:
        return "***NONE***"

    hdr = parse.of_header_parse(pkt)
    if not hdr:
        res = "Could not parse OpenFlow header, pkt len: " + len(pkt)
        return res
    if hdr.length == 0:
        res = "Header length is zero"
        return res
    else:
        return str(hdr.show())


def _pktParse(pkt):
    """
    OpenFlow message parser used for logging
    @param pkt a packed packet. If it is an OpenFlow message, used for parsing
    @return parsed information as a string, error message if parsing failed
    """
    if pkt is None:
        return "***NONE***"

    offset = 0
    hdr = parse.of_header_parse(pkt[offset:])
    if not hdr:
        res = "Could not parse OpenFlow header, pkt len: " + len(pkt)
        return res
    if hdr.length == 0:
        res = "Header length is zero"
        return res

    # Extract the raw message bytes
    rawmsg = pkt[offset : offset + hdr.length]
    msg = parse.of_message_parse(rawmsg)
    if not msg:
        res = "Could not parse message"
        return res
    else:
        return str(msg.show())


def test_param_get(config, key, default=None):
    """
    Return value passed via test-params if present

    @param config The configuration structure for test
    @param key The lookup key
    @param default Default value to use if not found

    If the pair 'key=val' appeared in the string passed to --test-params
    on the command line, return val (as interpreted by exec).  Otherwise
    return default value.
    """
    try:
        exec config["test_params"]
    except:
        return default

    s = "val = " + str(key)
    try:
        exec s
        return val
    except:
        return default
