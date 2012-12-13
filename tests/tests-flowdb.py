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
    basic_logger = logging.getLogger("flowdb")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


def _genFlowModArp(parent, dl_src = testutils.SRC_MAC_FOR_CTL0_0, dl_dst="00:01:02:03:04:05", out_ports=[0]):
    """
    Create flow_mod with arp matching that matches controller0 using given limited parameters
    Other parameters are chosen at random
    """
    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst=dl_dst, dl_type=testutils.ETHERTYPE_ARP, nw_proto=testutils.ARP_REPLY)

    action_list = []
    for port in out_ports:
        act = action.action_output()
        act.port = port
        action_list.append(act)
    flow_mod = testutils.genFloModFromPkt(parent, pkt, ing_port=0, action_list=action_list)

    return flow_mod

def _genFlowRemovedFromFlowMod(flow_mod):
    """
    Generate flow_removed using given flow_mod message
    Other parameters below are chosen at random
    """
    flow_removed = message.flow_removed()
    flow_removed.match = flow_mod.match
    flow_removed.cookie = flow_mod.cookie
    flow_removed.priority = flow_mod.priority
    flow_removed.duration_sec = 10 #random pick
    flow_removed.duration_nsec = 876 #random pick
    flow_removed.reason = ofp.OFPRR_IDLE_TIMEOUT
    flow_removed.packet_count = 5 #random pick
    flow_removed.byte_count = 23456 #random pick
    return flow_removed

def _genFlowModArpFlush(parent, wildcards=0x3fffff, in_port=0, dl_src="00:00:00:00:00:00"):
    flow_mod_flush = _genFlowModArp(parent, dl_src=dl_src, dl_dst="00:00:00:00:00:00", out_ports=[])
    flow_mod_flush.match.wildcards = wildcards
    flow_mod_flush.match.in_port = in_port
    #zero-out
    flow_mod_flush.match.dl_type = 0
    flow_mod_flush.match.dl_vlan = 0
    flow_mod_flush.match.nw_proto = 0
    flow_mod_flush.command = ofp.OFPFC_DELETE
    return flow_mod_flush


class TrackOff(templatetest.TemplateTest):
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
        # Prepare three flow_mods for controller0 and insert them
        (flow_mod1, flow_mod2, flow_mod3) = self.insertFlowMod()

        # Check flowDB. Since 'track mode' is NOT on, 'zero' is expected
        exp_count = 0
        res = testutils.chkFlowdb(self, controller_number=0, switch_number=0, exp_count=exp_count)
        self.assertTrue(res, "%s: CheckFlowDB: Flow is not %d" %(self.__class__.__name__, exp_count))

    def insertFlowMod(self):
        # Prepare three flow_mods for controller0
        # Flowmod1: outport=2
        flow_mod1 = _genFlowModArp(self, dl_dst = "00:0c:29:c6:36:8d", out_ports=[2])
        # Flowmod2: different dst mac from flomod1, same outport
        flow_mod2 = _genFlowModArp(self, dl_dst = "00:1c:29:c6:36:8d", out_ports=[2])
        # Flowmod3: Flood
        flow_mod3 = _genFlowModArp(self, dl_dst = "00:2c:29:c6:36:8d", out_ports=[ofp.OFPP_FLOOD])
        # Flowmod3(expected): Expanded command
        flow_mod3_exp = _genFlowModArp(self, dl_dst = "00:2c:29:c6:36:8d", out_ports=[2, 3])

        # Now send those three commands and verify them
        snd_list = ["controller", 0, 0, flow_mod1]
        exp_list = [["switch", 0, flow_mod1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod1: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["controller", 0, 0, flow_mod2]
        exp_list = [["switch", 0, flow_mod2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod2: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["controller", 0, 0, flow_mod3]
        exp_list = [["switch", 0, flow_mod3_exp]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod3: Received unexpected message" %(self.__class__.__name__))

        return (flow_mod1, flow_mod2, flow_mod3)


class TrackOn(TrackOff):
    """
    Flow_mod w/ tracking
    Send flowmod messages and check flowdb status
    Check if it is not updated since tracking is off in this test
    """
    def runTest(self):
        # Enable tracking
        rule = ["setFlowTracking", "True"]
        (success, stats) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Could not enable flow track" %(self.__class__.__name__))

        # Prepare three flow_mods for controller0 and insert them
        (flow_mod1, flow_mod2, flow_mod3) = TrackOff.insertFlowMod(self)

        # Check flowDB. This time the number of flows must be three
        exp_count = 3
        res = testutils.chkFlowdb(self, controller_number=0, switch_number=0, exp_count=exp_count)
        self.assertTrue(res, "%s: CheckFlowDB: Flow is not %d" %(self.__class__.__name__, exp_count))

        # Make one of the flows expire
        flow_rm1 = _genFlowRemovedFromFlowMod(flow_mod1)
	flow_rm1.cookie = 256
	flow_rm2 = _genFlowRemovedFromFlowMod(flow_mod1) 
	flow_rm2.cookie = 0


        snd_list = ["switch", 0, flow_rm1]
        exp_list = [["controller", 0, flow_rm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowRemoved: Received unexpected message" %(self.__class__.__name__))

        # Check flowDB. The number of flows must be now two
        exp_count = exp_count-1
        res = testutils.chkFlowdb(self, controller_number=0, switch_number=0, exp_count=exp_count)
        self.assertTrue(res, "%s: CheckFlowDB: Flow is not %d" %(self.__class__.__name__, exp_count))

        # Flow_mod flush with all wildcarded
        # FV will expand it to match only given conditions
        # In this test, the conditions are ports and dl_src
        flow_mod_flush = _genFlowModArpFlush(self)
        # Two dl_src conditions x three port conditions = 6 expanded commands are expected
        flow_mod_flush_exp1 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=0, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp2 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=0, dl_src=testutils.SRC_MAC_FOR_CTL0_1)
        flow_mod_flush_exp3 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=2, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp4 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=2, dl_src=testutils.SRC_MAC_FOR_CTL0_1)
        flow_mod_flush_exp5 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=3, dl_src=testutils.SRC_MAC_FOR_CTL0_0)
        flow_mod_flush_exp6 = _genFlowModArpFlush(self, wildcards= 0x3ffffa, in_port=3, dl_src=testutils.SRC_MAC_FOR_CTL0_1)

        snd_list = ["controller", 0, 0, flow_mod_flush]
        exp_list = [["switch", 0, flow_mod_flush_exp1],
                    ["switch", 0, flow_mod_flush_exp2],
                    ["switch", 0, flow_mod_flush_exp3],
                    ["switch", 0, flow_mod_flush_exp4],
                    ["switch", 0, flow_mod_flush_exp5],
                    ["switch", 0, flow_mod_flush_exp6]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowModFlush: Received unexpected message" %(self.__class__.__name__))

        # Check flowDB. All the flows should be deleted
        exp_count = 0
        res = testutils.chkFlowdb(self, controller_number=0, switch_number=0, exp_count=exp_count)
        self.assertTrue(res, "%s: CheckFlowDB: Flow is not %d" %(self.__class__.__name__, exp_count))
