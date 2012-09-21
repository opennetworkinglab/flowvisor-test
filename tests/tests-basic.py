"""
Simple tests exchanging OFprotocol btwn sw and ctl via FV
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
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
    basic_logger = logging.getLogger("basic")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class PktInPerPort(templatetest.TemplateTest):
    """
    Packet_in per port
    Check if packet_in message goes to expected controller depending on which
    switch port it came from
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        # Packet_in for controller0
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL0_0)
        in_port = 0 #CTL0 has this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # Packet_in for controller1
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL1_0)
        in_port = 1 #CTL1 has this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 1, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PktInPerSrcMac(PktInPerPort):
    """
    Packet_in per source MAC address
    Check if packet_in message goes to expected controller depending on
    which slice the source MAC address of the packet belongs to
    In this test, packets come from a shared port for both two slices
    """
    def runTest(self):
        # Packet_in for controller0
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL0_0)
        in_port = 3 #CTL0 and CTL1 share this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # Packet_in for controller1
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL1_0)
        in_port = 3 #CTL0 and CTL1 share this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 1, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class Echo(PktInPerPort):
    """
    Echo_request and echo_reply
    Check if echo_request is terminated by FlowVisor and echo_reply
    comes back from it (not from target switch or controller)
    """
    def runTest(self):
        msg = message.echo_request()
        exp_msg = message.echo_reply()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["controller", 1, 0, msg]
        exp_list = [["controller", 1, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["switch", 0, msg]
        exp_list = [["switch", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PortStatus(PktInPerPort):
    """
    Port_status
    Check if port_status from switch goes to expected contoroller depending
    on which switch port it came from
    """
    def runTest(self):
        port0 = testutils.genPhyPort("port0", [00,0x22,0x44,0x66,0x88,0xaa], 0)
        msg = message.port_status()
        msg.reason = ofp.OFPPR_ADD
        msg.desc = port0

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        port1 = testutils.genPhyPort("port1", [00,0x11,0x33,0x55,0x77,0x99], 1)
        msg = message.port_status()
        msg.reason = ofp.OFPPR_ADD
        msg.desc = port1

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 1, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PaktOutCorrect(PktInPerPort):
    """
    Packet_out with packet within slice conditions
    Check packet_out from a controller goes to switch
    if the packet matches the conditions of slice
    """
    def runTest(self):
        ports_ctl = [0]
        pkt_ctl = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PaktOutError(PktInPerPort):
    """
    Packet_out with packet out of slice conditions
    Check controller gets error message when throwing packet_out
    if the packet doesn't match the conditions of slice
    In this test, source MAC address doesn't match
    """
    def runTest(self):
        ports_ctl = [0]
        pkt_ctl = testutils.simplePacket(dl_src="00:00:00:00:00:00")
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        err_msg = error.bad_action_error_msg()
        err_msg.code = ofp.OFPBRC_BAD_LEN
        err_msg.data = pktout_ctl.pack()

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["controller", 0, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: PacketOut: Received unexpected message" %(self.__class__.__name__))

        # Check everyone is sill alive after the error by sending echo
        msg = message.echo_request()
        exp_msg = message.echo_reply()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Echo: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["controller", 1, 0, msg]
        exp_list = [["controller", 1, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Echo: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["switch", 0, msg]
        exp_list = [["switch", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Echo: Received unexpected message" %(self.__class__.__name__))


class DescStats(PktInPerPort):
    """
    Desc_stats_request and desc_stats_reply
    Check if desc_stats_request goes from controller to switch, and
    check desc_Stats_reply comes back from switch to controller
    """
    def runTest(self):
        # Desc stats request
        msg = message.desc_stats_request()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Req: Received unexpected message" %(self.__class__.__name__))

        #Desc stats reply
        desc = ofp.ofp_desc_stats()
        desc.mfr_desc= "ONL"
        desc.hw_desc= "Fake Switch for Flowvisor Testing"
        desc.sw_desc= "Test software"
        desc.serial_num= "01234567"
        desc.dp_desc= "No datapath on this switch"
        msg = message.desc_stats_reply()
        msg.header.xid = ret_xid
        msg.stats.append(desc)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Rep: Received unexpected message" %(self.__class__.__name__))


class PktOutFlood(PktInPerPort):
    """
    Packet_out with flood port
    Check that pakcet_out to flood port from controller is modified and FlowVisor
    only specifies the ports each slice has
    """
    def runTest(self):
        # From ctl0. Should be expanded for switch
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [0,2,3]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw, pkt=pkt_ctl)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # From ctl1. Should be expanded for switch
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL1_0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [1,3]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw, pkt=pkt_ctl)

        snd_list = ["controller", 1, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PktOutShort(PktInPerPort):
    """
    Packet_out with short packet
    Check that Pakcet_out which has short size packet can go through
    FlowVisor to switch
    """
    def runTest(self):
        ports_ctl = [0]
        pkt_ctl = testutils.simplePacket(pktlen=14, dl_src=testutils.SRC_MAC_FOR_CTL0_0, dl_type=0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PktOutBufId(PktInPerPort):
    """
    Packet_out with specific buffer_id
    Check that Pakcet_out using buffer_id of packet_in goes to switch
    Check only the controller which has received the packet_in can perform
    this packet_out
    """
    def runTest(self):
        buffer_id = 0x12345678
        pkt = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        msg = testutils.genPacketIn(buffer_id=buffer_id, in_port=0, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Packet_in: Received unexpected message" %(self.__class__.__name__))

        ports_ctl = [0]
        pktout_ctl = testutils.genPacketOut(self, buffer_id=buffer_id, action_ports=ports_ctl, pkt=None)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_ctl]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Packet_out: Received unexpected message" %(self.__class__.__name__))

        err_msg = error.bad_request_error_msg()
        err_msg.code = ofp.OFPBRC_BUFFER_UNKNOWN
        err_msg.data = pktout_ctl.pack()

        snd_list = ["controller", 1, 0, pktout_ctl]
        exp_list = [["controller", 1, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Packet_out: Received unexpected message" %(self.__class__.__name__))


class Vendor(PktInPerPort):
    """
    Vendor message
    Check if vendor message goes straight to switch
    """
    def runTest(self):
        msg = message.vendor()
        msg.code = 0x2 # random pick
        msg.data = "0123456789abcdef" # random pick

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class PortStats(PktInPerPort):
    """
    Port_stats request
    Check if port_stats request message goes straight to switch
    """
    def runTest(self):
        msg = message.port_stats_request()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
