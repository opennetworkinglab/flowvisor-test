"""
Packet_in tests w/ and w/o VLAN tag
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action
import time

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
    basic_logger = logging.getLogger("vlan")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------

def _genFlowModVlan(parent, src_vid = 1, dst_vid = 2, in_port = 1,out_port = 2):
    flow_mod = message.flow_mod()
    flow_mod.match.wildcards = ofp.OFPFW_ALL & ~ofp.OFPFW_IN_PORT &  ~ofp.OFPFW_DL_VLAN
    flow_mod.match.dl_vlan = src_vid
    flow_mod.match.in_port = in_port
    flow_mod_command = ofp.OFPFC_ADD
    flow_mod.priority = 0
    flow_mod.buffer_id = 0xFFFFFFFF
    output_act = action.action_output()
    output_act.port = out_port
    flow_mod.actions.add(output_act)
    vlan_act = action.action_set_vlan_vid()
    vlan_act.vlan_vid =  dst_vid
    flow_mod.actions.add(vlan_act)
    return flow_mod   


class NoVlan1(templatetest.TemplateTest):
    """
    Non Vlan packet_in when vlan matching is in the slice rules
    Check if it doesn't match the slice with vlan
    In this test the packet should go to controller1
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Prepare additional rules to set
        rule1 = ["changeFlowSpace", "ADD", "33000", "all", "dl_vlan=812", "Slice:controller0=4"]
        rule2 = ["listFlowSpace"]
        rules = [rule1, rule2]
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, rules=rules)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        pkt_no_vlan = testutils.simplePacket(pktlen=64, dl_src=testutils.SRC_MAC_FOR_CTL1_1)
        packet_in_no_vlan = testutils.genPacketIn(pkt=pkt_no_vlan)

        snd_list = ["switch", 0, packet_in_no_vlan]
        exp_list = [["controller", 1, packet_in_no_vlan]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class NoVlan2(NoVlan1):
    """
    Non Vlan packet_in when vlan matching is in the slice rules
    Check if it doesn't match the slice with vlan
    In this test the packet should go to controller1
    """
    def runTest(self):
        # Case2: Should go to controller1
        pkt_no_vlan = testutils.simplePacket(pktlen=64, dl_src=testutils.SRC_MAC_FOR_CTL1_1, dl_dst='00:00:00:00:00:01')
        packet_in_no_vlan = testutils.genPacketIn(pkt=pkt_no_vlan)

        snd_list = ["switch", 0, packet_in_no_vlan]
        exp_list = [["controller", 1, packet_in_no_vlan]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class Vlan1(NoVlan1):
    """
    Vlan packet_in when vlan matching is in the slice rules
    Check it doesn't match the slice with vlan when VlanID doesn't match
    In this test the packet should go to controller1
    """
    def runTest(self):
        pkt_vlan = testutils.simplePacket(pktlen=64, dl_src=testutils.SRC_MAC_FOR_CTL1_1, dl_vlan=1)
        packet_in_vlan = testutils.genPacketIn(pkt=pkt_vlan)

        snd_list = ["switch", 0, packet_in_vlan]
        exp_list = [["controller", 1, packet_in_vlan]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class Vlan2(NoVlan1):
    """
    Vlan packet_in when vlan matching is in the slice rules
    Check if it matches the slice with vlan
    in this test the packet should go to controller0
    """
    def runTest(self):
        pkt_vlan = testutils.simplePacket(pktlen=64, dl_src=testutils.SRC_MAC_FOR_CTL1_1, dl_dst='00:00:00:00:00:01', dl_vlan=812)
        packet_in_vlan = testutils.genPacketIn(pkt=pkt_vlan)

        snd_list = ["switch", 0, packet_in_vlan]
        exp_list = [["controller", 0, packet_in_vlan]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

class Internet2_Vlans(templatetest.TemplateTest):
    """
    Internet2 guys claim that FV overwrites their inport when using vlans
    with FV rules which wildcard the inport.

    This test check whether pushing a flow mod with a vlan tag and an inport
    is overwritten erroneously by flowvisor.
    """

    def runTest(self):
        rule1 = ["changeFlowSpace", "ADD", "33000", "00:00:00:00:00:00:00:00", "dl_vlan=1", "Slice:controller0=4"]
        rule2 = ["changeFlowSpace", "ADD", "33000", "00:00:00:00:00:00:00:00", "dl_vlan=2", "Slice:controller0=4"]

        rule3 = ["listFlowSpace"]
        rules = [rule1, rule2, rule3]
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, rules=rules)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)
        fm = _genFlowModVlan(self)
        snd_list = ["controller", 0, 0, fm]
        exp_list = [["switch", 0, fm]]

        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: flowmod: Received unexpected message" %(self.__class__.__name__))
        time.sleep(5)
        return fm

        

