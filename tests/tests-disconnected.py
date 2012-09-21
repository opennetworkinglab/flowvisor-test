"""
Packet_in tests to disconnected controller
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
    basic_logger = logging.getLogger("disconn")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class PktIn2Disconn(templatetest.TemplateTest):
    """
    Packet_in to disconnected controller
    When FlowVisor has received packet_in to disconnected controller,
    check it discards it and send FlowMod with drop to the switch
    In this test, it sends pkt_in from switch to connected controller
    Check it is received
    Then it sends pkt_in to not-connected controller
    Check FlowVisor sends flow_mod_drop msg to switch
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 2, num of CTL = 1
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, num_of_switches=2, num_of_controllers=1)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        # Prepare messages for sending and expecting
        pkt_for_ctl0 = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        pkt_in_for_ctl0 = testutils.genPacketIn(in_port=0, pkt=pkt_for_ctl0)

        pkt_for_ctl1 = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL1_0)
        pkt_in_for_ctl1 = testutils.genPacketIn(in_port=1, pkt=pkt_for_ctl1)

        flow_mod_drop_sw0 = testutils.genFloModFromPkt(self, pkt_for_ctl1, ing_port=1)
        flow_mod_drop_sw0.idle_timeout = 1
        flow_mod_drop_sw0.priority = 0
        flow_mod_drop_sw0.buffer_id = 0
        flow_mod_drop_sw0.flags = ofp.OFPFF_SEND_FLOW_REM

        # controller0 should receive the msg from sw0
        snd_list = ["switch", 0, pkt_in_for_ctl0]
        exp_list = [["controller", 0, pkt_in_for_ctl0]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # packet_in for controller1 should be dropped and FV should generate drop msg to sw0
        snd_list = ["switch", 0, pkt_in_for_ctl1]
        exp_list = [["switch", 0, flow_mod_drop_sw0]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class Lldp2nobody(PktIn2Disconn):
    """
    LLDP from switch to nobody
    Check that un-trailered LLDP message from switch goes to controller
    without modification
    """
    def runTest(self):
        # Generate packet_in with LLDP for nobody (can use the default parameter values)
        lldp = testutils.simpleLldpPacket()
        pkt_in_lldp = testutils.genPacketIn(in_port=3, pkt=lldp)

        # controller0 should receive the same msg
        snd_list = ["switch", 0, pkt_in_lldp]
        exp_list = [["controller", 0, pkt_in_lldp]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
