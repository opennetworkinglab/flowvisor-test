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
    basic_logger = logging.getLogger("flowlimit")
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



class RateLimit(templatetest.TemplateTest):

    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, \
                            num_of_switches=2, num_of_controllers=2)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    """
    Test Global slice limit.
    
    After the maximum number of rules have been installed,
    FlowVisor should push an error back to the controller.
    """
    def runTest(self):

        max = 3
        rule = ["setRateLimit", "controller0",  str(max)]
        (success, stats) = testutils.setRule(self, self.sv, rule)
        self.logger.info("Setting rate limit to %s" % max)
        self.assertTrue(success, "%s: Could not set rate limit" %(self.__class__.__name__))

    	fm1 = _genFlowModArp(self, out_ports = [0])
    	fm2 = _genFlowModArp(self, out_ports = [2])
    	fm3 = _genFlowModArp(self, out_ports = [3])
    	fm4 = _genFlowModArp(self, dl_dst="DE:AD:BE:EF:CA:FE", out_ports = [0])

    	snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod1: Received unexpected message" %(self.__class__.__name__))

    	snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod2: Received unexpected message" %(self.__class__.__name__))

        snd_list = ["controller", 0, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: FlowMod3: Received unexpected message" %(self.__class__.__name__))


        err_msg = error.flow_mod_failed_error_msg()
        err_msg.code = ofp.OFPFMFC_EPERM
        err_msg.data = fm4.pack()

        snd_list = ["controller", 0, 0, fm4]
        exp_list = [["controller", 0, err_msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, hdr_only=True)
        self.assertTrue(res, "%s: RateLimit: Received unexpected message" %(self.__class__.__name__))


