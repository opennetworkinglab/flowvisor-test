"""
Stats tests and error/illegal conditions tests
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action
import oftest.error as error
import oftest.parse as parse

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
    basic_logger = logging.getLogger("safety")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


def _genFlowModFlushAll(parent, wildcards=0x3fffff, in_port=0, dl_src="00:00:00:00:00:00"):
    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst="00:00:00:00:00:00", dl_type=testutils.ETHERTYPE_ARP, nw_proto=testutils.ARP_REPLY)
    flow_mod_flush = testutils.genFloModFromPkt(parent, pkt, ing_port=in_port, wildcards=wildcards)
    # Zero out for flush msg
    flow_mod_flush.match.dl_type = 0
    flow_mod_flush.match.dl_vlan = 0
    flow_mod_flush.match.nw_proto = 0
    flow_mod_flush.command = ofp.OFPFC_DELETE
    return flow_mod_flush


class EchoPayload(templatetest.TemplateTest):
    """
    Echo_request with Payload
    Check if FlowVisor pass the echo_request with payload
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)




    def runTest(self):
        msg = message.echo_request()
        msg.data = "FlowVisor Testing"
        exp_msg = message.echo_reply()
        exp_msg.data = msg.data

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class FeatReqErr(EchoPayload):
    """
    Features_request and its error_reply
    First, make up a features_request and exchange error message
    This test is about Flowvisor's XID mapping works fine
    """
    def runTest(self):
        msg = message.features_request()
        msg.header.xid = testutils.genVal32bit()
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FeatReq: Received unexpected message" %(self.__class__.__name__))

        err = error.bad_request_error_msg()
        err.header.xid = ret_xid
        err.code = ofp.OFPBRC_BUFFER_UNKNOWN
        err.data = msg.pack()

        snd_list = ["switch", 0, err]
        exp_list = [["controller", 0, err]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: BadReqErr: Received unexpected message" %(self.__class__.__name__))


class FlowModFail(EchoPayload):
    """
    Flow_mod to erase all and its error_reply
    Send a 'flow_mod erase all' and FlowVisor expands it so that
    it can exclude non-matching conditions
    Assume it causes an error
    Check these message exchange are successful
    In this test, the matching conditions are ports and dl_src
    """
    def runTest(self):
        # Flow_mod erase all
        flow_mod_flush = _genFlowModFlushAll(self)

        # Two dl_src conditions x three port conditions = 6 expanded commands
        flow_mod_flush_exp1 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=0, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp2 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=0, dl_src=testutils.SRC_MAC_FOR_CTL0_1)
        flow_mod_flush_exp3 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=2, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp4 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=2, dl_src=testutils.SRC_MAC_FOR_CTL0_1)
        flow_mod_flush_exp5 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=3, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp6 = _genFlowModFlushAll(self, wildcards= 0x3ffffa, in_port=3, dl_src=testutils.SRC_MAC_FOR_CTL0_1)

        snd_list = ["controller", 0, 0, flow_mod_flush]
        exp_list = [["switch", 0, flow_mod_flush_exp1],
                    ["switch", 0, flow_mod_flush_exp2],
                    ["switch", 0, flow_mod_flush_exp3],
                    ["switch", 0, flow_mod_flush_exp4],
                    ["switch", 0, flow_mod_flush_exp5],
                    ["switch", 0, flow_mod_flush_exp6]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod: Received unexpected message" %(self.__class__.__name__))

        # Check flowDB. All the flows should be deleted
        res = testutils.chkFlowdb(self, controller_number=0, switch_number=0, exp_count=0)
        self.assertTrue(res, "%s: ChkFlowDB: Flow is not deleted" %(self.__class__.__name__))

        err = error.flow_mod_failed_error_msg()
        err.header.xid = ret_xid
        err.code = ofp.OFPFMFC_EPERM

        snd_list = ["switch", 0, err]
        exp_list = [["controller", 0, err]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowModErr: Received unexpected message" %(self.__class__.__name__))


class OldOFVer(EchoPayload):
    """
    Echo_request with old OpenFlow version
    When controller sends echo_request with old OpenFlow version,
    check if it gets echo_reply with current OpenFlow version
    (FlowVisor terminates echo message)
    """
    def runTest(self):
        msg = message.echo_request()
        msg.header.version = 0x97
        exp_msg = message.echo_reply()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, exp_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class Pkt2DelSlice(EchoPayload):
    """
    Packet_in to dynamically deleted slice
    After deleting a slice, make sure the controller cannot
    receive packet_in from switch via FlowVisor
    """
    def runTest(self):
        rule = ["deleteSlice", "controller0"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: DelSlice: Not success" %(self.__class__.__name__))

        # Check the number of flow space
        rule = ["listFlowSpace"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: ListFlowSpace: Not success" %(self.__class__.__name__))
        self.assertFalse(("controller0" in data), "%s: Failed slice deletion" %(self.__class__.__name__))

        # Packet_in for controller0
        # Should not be received
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL0_0)
        in_port = 0 #CTL0 has this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, None]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

        # Packet_in for controller1
        # Should be received
        pkt = testutils.simplePacket(dl_src = testutils.SRC_MAC_FOR_CTL1_0)
        in_port = 1 #CTL1 has this port
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 1, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
