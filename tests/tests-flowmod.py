"""
Flow_mod + FlowDB verification tests
 - Send flow_mods, then check flow_db w/o flow track. Make sure they aren't counted
 - With 'track mode' ON, do the same test as above and check the number of flows
 - Send flow_removed from sw, then check number of flows is decremented
 - Send flow_mod_flush, check if it is correctly expanded, then check flow_db has zero flows
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.parse as parse
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
    basic_logger = logging.getLogger("flowmod")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


def _genFlowModArp(parent, wildcards=0x3ffffa, dl_src = testutils.SRC_MAC_FOR_CTL0_0, dl_dst="00:00:00:00:00:00", out_ports=[0]):
    """
    Create flow_mod with arp matching that matches controller0 using given limited parameters
    Other parameters are chosen at random
    """
    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst=dl_dst, dl_type=0, dl_vlan=0, tp_src=0,tp_dst=0)

    action_list = []
    for port in out_ports:
        act = action.action_output()
        act.port = port
        action_list.append(act)
    flow_mod = testutils.genFloModFromPkt(parent, pkt, ing_port=0, action_list=action_list)
    flow_mod.match.wildcards = wildcards
    return flow_mod

class ExpandNot(templatetest.TemplateTest):
    """
    Flow_mod w/o tracking
    Send flowmod messages and check flowdb status
    Check if it is not updated since tracking is off in this test
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        buffer_id = 0x12345678
        pkt = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        msg = testutils.genPacketIn(buffer_id=buffer_id, in_port=0, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Packet_in: Received unexpected message" %(self.__class__.__name__))

        flowmod = _genFlowModArp(self,out_ports=[2])
        flowmod.buffer_id = buffer_id

        snd_list = ["controller", 0, 0, flowmod]
        exp_list = [["switch", 0, flowmod]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod_ExpandNot: Received unexpected message" %(self.__class__.__name__))
       
class Expand(templatetest.TemplateTest):
    """
    Flow_mod w/o tracking
    Send flowmod messages and check flowdb status
    Check if it is not updated since tracking is off in this test
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        buffer_id = 0x12345678
        pkt = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        msg = testutils.genPacketIn(buffer_id=buffer_id, in_port=0, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Packet_in: Received unexpected message" %(self.__class__.__name__))

        flowmod = _genFlowModArp(self,wildcards=0x3fffff,dl_src="00:00:00:00:00:00",out_ports=[2])
        flowmod.buffer_id = buffer_id

        flowmod_exp = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        flowmod_exp.buffer_id = buffer_id

        flowmod_exp1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])

        snd_list = ["controller", 0, 0, flowmod]
        exp_list = [["switch", 0, flowmod_exp],
                    ["switch", 0, flowmod_exp1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))

   
