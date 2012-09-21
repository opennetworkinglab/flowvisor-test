"""
Ping and lldp related tests
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.parse as parse
import oftest.action as action
import oftest.error as error

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
    basic_logger = logging.getLogger("readonly")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class PktInPing(templatetest.TemplateTest):
    """
    Pakcet_in with ping as a packet
    Check if controller gets it when the packet inside packet_in
    matches its flow space
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        pkt = testutils.simplePacket(
            nw_proto=testutils.IPPROTO_ICMP,
            dl_src=testutils.SRC_MAC_FOR_CTL1_0,
            tp_src=testutils.ECHO_REQUEST,
            tp_dst=0)
        msg = testutils.genPacketIn(in_port=1, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 1, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PktOutLldp(PktInPing):
    """
    Packet_out with LLDP packet
    Check that when controller sends a valid LLDP packet, FlowVisor
    adds 'trailer' before is sends it to switch
    """
    def runTest(self):
        ports = [0]
        in_port = ofp.OFPP_CONTROLLER
        lldp_ctl = testutils.simpleLldpPacket(dl_dst="f1:23:20:00:00:01",
                                              dl_src="00:21:5c:54:a6:a1")
        pktout_ctl = testutils.genPacketOut(self, in_port=in_port, action_ports=ports, pkt=lldp_ctl)

        trailer = testutils.genTrailer("controller0", "    magic flowvisor1")
        lldp_sw = testutils.simpleLldpPacket(dl_dst="f1:23:20:00:00:01",
                                             dl_src="00:21:5c:54:a6:a1",
                                             trailer=trailer)
        pktout_sw = testutils.genPacketOut(self, in_port=in_port, action_ports=ports, pkt=lldp_sw)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class LldpErr1(PktInPing):
    """
    LLDP-ish irregular message and its error response
    Check that even if the packet in packet_out is LLDP-ish packet,
    if the dl_type is different send back error message to controller
    The send-back error message should be OFPED_BAD_ACTION, OFPBAC_EPERM
    """
    def runTest(self):
        ports_ctl = [0]
        dummy_lldp = testutils.simpleLldpPacket(dl_type=0x88aa)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=dummy_lldp)

        err_msg = error.bad_action_error_msg()
        err_msg.code = ofp.OFPBAC_EPERM
        err_msg.data = pktout_ctl.pack()

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["controller", 0, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class LldpErr2(PktInPing):
    """
    LLDP-ish irregular message and its error response
    Check that even if the packet in packet_out is LLDP-ish packet and
    and even if the dl_type is different, if the buffer_id is incorrect,
    send back error message to controller
    The send-back error message should be OFPED_BAD_REQUEST, OFPBRC_BUFFER_UNKNOWN
    """
    def runTest(self):
        buffer_id_ctl = 0x12345678 #dummy
        ports_ctl = [0]
        dummy_lldp = testutils.simpleLldpPacket(dl_type=0x88aa)
        pktout_ctl = testutils.genPacketOut(self, buffer_id=buffer_id_ctl, action_ports=ports_ctl, pkt=dummy_lldp)

        err_msg = error.bad_request_error_msg()
        err_msg.code = ofp.OFPBRC_BUFFER_UNKNOWN
        err_msg.data = pktout_ctl.pack()

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["controller", 0, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class BrokenFlowMod(PktInPing):
    """
    Flow_mod with misaligned fields
    When controller sends misaligned flow_mod, FlowVisor should
    reject it and send back error message with permission_error
    """
    def runTest(self):
        bad_match = ofp.ofp_match()
        bad_match.wildcards = 0
        bad_match.in_port = 2
        bad_match.dl_dst = parse.parse_mac("00:10:18:07:67:87")
        bad_match.dl_src = parse.parse_mac("00:0d:b9:15:c0:44")
        bad_match.dl_type = 0x1100
        bad_match.dl_vlan = 0xffff
        bad_match.dl_vlan_pcp = 0x08
        bad_match.nw_src = 0xc0a80202
        bad_match.nw_dst = 0x00430044
        bad_match.nw_tos = 0xc0
        bad_match.nw_proto = 0xa8
        bad_match.pad2 = [0x02, 0xfe]
        bad_match.tp_src = 0
        bad_match.tp_dst = 5

        bad_flow_mod = message.flow_mod()
        bad_flow_mod.header.xid = testutils.genVal32bit()
        bad_flow_mod.match = bad_match
        bad_flow_mod.cookie = 0x0000800000177097
        bad_flow_mod.command = 0x406f
        bad_flow_mod.priority = 0
        bad_flow_mod.buffer_id = 0xffffffff
        bad_flow_mod.out_port = 1

        err_msg = error.flow_mod_failed_error_msg()
        err_msg.code = ofp.OFPFMFC_EPERM
        err_msg.data = bad_flow_mod.pack()

        snd_list = ["controller", 0, 0, bad_flow_mod]
        exp_list = [["controller", 0, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, hdr_only=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
