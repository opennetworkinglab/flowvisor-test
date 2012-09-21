"""
API (Flow Stats Request) test
Send one flow_stats request and check if it is received on switch
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action
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
    basic_logger = logging.getLogger("flowstats")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class FlowStats(templatetest.TemplateTest):
    """
    FlowStats checking after deleting slices
    It spawns flowvisor with two slices, spawns several switches,
    deletes slices and check the number of remaining slices
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: setting: config_file = test-base.xml, num of SW = 2, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, num_of_switches=2, num_of_controllers=2)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        # Matching field values below are from original regression test case
        match = ofp.ofp_match()
        match.wildcards = 0xFFFFFFFF
        match.dl_dst = parse.parse_mac("00:00:00:00:00:00")
        match.dl_src = parse.parse_mac("00:00:00:00:00:00")
        match.dl_type = 0
        match.dl_vlan = 0
        match.dl_vlan_pcp = 0
        match.nw_src = parse.parse_ip("0.0.0.0")
        match.nw_dst = parse.parse_ip("0.0.0.0")
        match.nw_tos = 0
        match.nw_proto = 0
        match.tp_src = 0
        match.tp_dst = 0

        msg = message.flow_stats_request()
        msg.header.xid = testutils.genVal32bit()
        msg.match = match
        msg.table_id = 0xff
        msg.out_port = 0xffff

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
