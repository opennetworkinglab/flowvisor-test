"""
Packet_out to flood-port tests
If a slice rule specifies only a portion of the switch ports,
The packet_out_flood from the controller will be modified in FlowVisor
so that it can specify multiple specific ports
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action

# ------ Start: Mandatory portion on each test case file ------

#@var basic_port_map Local copy of the configuration map from OF port
# numbers to OS interfaces
basic_port_map = None
#@var basic_logger Local logger object
basic_logger = None
#@var basic_timeout Local copy of global timeout value
basic_timeout = None
#@var basic_config Local copy of global configuration data
basic_config = None

test_prio = {}

def test_set_init(config):
    """
    Set up function for basic test classes
    @param config The configuration dictionary; see fvt
    """
    global basic_port_map
    global basic_fv_cmd
    global basic_logger
    global basic_timeout
    global basic_config

    basic_fv_cmd = config["fv_cmd"]
    basic_logger = logging.getLogger("flood")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------

class FeaturesReply(templatetest.TemplateTest):
    """
    Features_request and features_reply with flood port
    Even if switch sends back information about all of its ports,
    FlowVisor should only send controller the information about the
    ports within the slice rule
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Prepare additional rules to set
        # If in_port is either 0,2 or 3, the msg will go to ctl0
        # But if dl_src is the specific value, it will go to ctl1 (higher priority)
        # Enable 'flood permission' so that flowvisor can pass 'flood' to switches
        rule1 = ["changeFlowSpace", "ADD", "33000", "all", "in_port=0", "Slice:controller0=4"]
        rule2 = ["changeFlowSpace", "ADD", "33000", "all", "in_port=2", "Slice:controller0=4"]
        rule3 = ["changeFlowSpace", "ADD", "33000", "all", "in_port=3", "Slice:controller0=4"]
        rule4 = ["changeFlowSpace", "ADD", "34000", "all", "dl_src=00:11:22:33:44:55", "Slice:controller1=4"]
        rule5 = ["setDefaultFloodPerm", "controller1"]
        rule6 = ["listFlowSpace"]
        rules = [rule1, rule2, rule3, rule4, rule5, rule6]
        #rules = [rule5, rule6]
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, rules=rules)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        # Send features_request from ctl0
        features_request = message.features_request()
        features_request.header.xid = testutils.genVal32bit()

        snd_list = ["controller", 0, 0, features_request]
        exp_list = [["switch", 0, features_request]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Req: Received unexpected message" %(self.__class__.__name__))

        # Features_reply from SW with four(0,1,2,3) ports
        # Only portion of the ports is visible to ctl0
        ports_sw = [0, 1, 2, 3]
        dpid = 1
        switch_features_sw = testutils.genFeaturesReply(ports=ports_sw, dpid=dpid)
        switch_features_sw.header.xid = ret_xid

        ports_ctl = [0, 2, 3]
        switch_features_ctl = testutils.genFeaturesReply(ports=ports_ctl, dpid=dpid)
        switch_features_ctl.header.xid = features_request.header.xid

        snd_list = ["switch", 0, switch_features_sw]
        exp_list = [["controller", 0, switch_features_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Rep: Received unexpected message" %(self.__class__.__name__))

        # Send features_request from ctl1
        features_request = message.features_request()
        features_request.header.xid = testutils.genVal32bit()

        snd_list = ["controller", 1, 0, features_request]
        exp_list = [["switch", 0, features_request]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Req: Received unexpected message" %(self.__class__.__name__))

        # Features_reply from SW with four(0,1,2,3) ports
        # All the ports are visible to ctl1
        ports_sw = [0, 1, 2, 3]
        dpid = 0
        switch_features_sw = testutils.genFeaturesReply(ports=ports_sw, dpid=dpid)
        switch_features_sw.header.xid = ret_xid

        ports_ctl = ports_sw
        switch_features_ctl = testutils.genFeaturesReply(ports=ports_ctl, dpid=dpid)
        switch_features_ctl.header.xid = features_request.header.xid

        snd_list = ["switch", 0, switch_features_sw]
        exp_list = [["controller", 1, switch_features_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Rep: Received unexpected message" %(self.__class__.__name__))


class PktOutFlood(FeaturesReply):
    """
    Packet_out to flood port
    Packet_out with Flood should be expanded if a slice has only
    portion of the switch ports
    """
    def runTest(self):
        # Packet out (flood) from 'ctl0'. Should be expanded for 'switch'
        ports_ctl = [ofp.OFPP_FLOOD]
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl)

        ports_sw = [0, 2, 3]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # Packet out (flood) from 'ctl1'. Should be transparent to 'switch'
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src="00:11:22:33:44:55")
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        snd_list = ["controller", 1, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PktOutNoFloodPort(FeaturesReply):
    """
    packet_out to flood port
    but set one port in slice to NO_FLOOD
    should expand to all ports except that one
    """

    def runTest(self):
        port_mod = message.port_mod()
        port_mod.port_no = 2
        port_mod.config = ofp.OFPPC_NO_FLOOD
        port_mod.mask = ofp.OFPPC_NO_FLOOD
        port_mod.advertise = 0
        
        snd_list = ["controller", 0, 0, port_mod]
        exp_list = [["switch", 0, None]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


        ports_ctl = [ofp.OFPP_FLOOD]
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl)

        ports_sw = [0, 3]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


        
