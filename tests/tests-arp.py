"""
Flow_mod (arp) test
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
    basic_logger = logging.getLogger("arp")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class FlowModArp(templatetest.TemplateTest):
    """
    Send flow_mod message with arp matching. Should be transparnt to switch
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 1
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, num_of_controllers = 1)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        pkt = testutils.simplePacket(dl_type=testutils.ETHERTYPE_ARP,
                                     nw_proto=testutils.ARP_REPLY,
                                     dl_src=testutils.SRC_MAC_FOR_CTL0_0,
                                     dl_dst="00:01:02:03:04:05",
                                     nw_src="192.168.0.1",
                                     nw_dst="192.168.1.1")
        act = action.action_output()
        act.port = 2
        flow_mod = testutils.genFloModFromPkt(self, pkt, ing_port=0, action_list=[act])
        flow_mod.header.xid =testutils.genVal32bit()
        flow_mod.command = ofp.OFPFC_ADD
        flow_mod.idle_timeout = 5
        flow_mod.match.wildcards = 192

        snd_list = ["controller", 0, 0, flow_mod]
        exp_list = [["switch", 0, flow_mod]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
