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
    basic_logger = logging.getLogger("flowlimit")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


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



class SliceLimit(templatetest.TemplateTest):

    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    """
    Flow_mod w/ tracking
    Send flowmod messages and check flowdb status
    Check if it is not updated since tracking is off in this test
    """
    def runTest(self):
        # Sertting maximum allowable flow mods to 10
        rule = ["setMaximumFlowMods", "controller0", "any", "10"]
        (success, stats) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Could not set the maximum allowable flowmods" %(self.__class__.__name__))

