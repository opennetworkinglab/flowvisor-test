"""
Stats tests
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
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
    basic_logger = logging.getLogger("port")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------

class PortStats(templatetest.TemplateTest):
    """
    Port_stats_request
    Check if switch gets the same port_stats message as controller has
    issued
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Prepare additional rules to set
        # Set a rule in addition to a default config,
        # Now controller0 handles packets with specific dl_src from/to any ports
        rule1 = ["changeFlowSpace", "ADD", "34000", "all", "dl_src=00:11:22:33:44:55", "Slice:controller0=4"]
        rule2 = ["listFlowSpace"]
        rules = [rule1, rule2]
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, rules=rules)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        msg = message.port_stats_request()
        msg.header.xid = testutils.genVal32bit()
        msg.port_no = ofp.OFPP_NONE

        # Ctl0
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class DescStats(templatetest.TemplateTest):
    """
    Desc_stats_request and desc_stats_reply
    Check if desc_stats_request goes from controller to switch, and
    check desc_Stats_reply comes back from switch to controller
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)


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


class TableStats(DescStats):
    """
    Table_stats request and reply
    Check if table_stats_request goes to switch through FlowVisor
    Check if table_stats_reply goes to controller through FlowVisor
    """
    def runTest(self):
        # Table_stats_request
        # Expect to receive same message on ctrl
        msg = message.table_stats_request()

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Req: Received unexpected message" %(self.__class__.__name__))

        # Table_stats_reply
        # Prepare table_stats information
        # Assume switch has two tables
        table0 = ofp.ofp_table_stats()
        table0.table_id = 0
        table0.name = "fvtest table0 exact"
        table0.wildcards = 0
        table0.max_entries = 0x100

        table1 = ofp.ofp_table_stats()
        table1.table_id = 1
        table1.name = "fvtest table1 wildcard"
        table1.wildcards = 0x3fffff
        table0.max_entries = 0x255

        stats = [table0, table1]

        msg = message.table_stats_reply()
        msg.header.xid = ret_xid
        msg.stats = stats

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Rep: Received unexpected message" %(self.__class__.__name__))


