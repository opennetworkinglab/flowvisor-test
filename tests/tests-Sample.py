import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.action as action
import re

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
    basic_logger = logging.getLogger("api")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------
NUM_SW = 2
NUM_CTL = 2

class Ping(templatetest.TemplateTest):
    """
    Ping and pong
    Check if FlowVisor receives ping from API client and sends back pong to it
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: setting: config_file = test-base.xml, num of SW = 2, num of CTL = 2
        #                   no additional rules
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, num_of_switches=NUM_SW, num_of_controllers=NUM_CTL)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        rule = ["list-version"]
        exp_data_fv = "flowvisor-version"
        exp_data_db = "db-version"
        # send the command and expect to receive pong
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        self.logger.info("Ping: Received: %s" % data)
        self.assertTrue(data.has_key(exp_data_fv), "%s: Received unexpected message" %(self.__class__.__name__))
        self.assertTrue(data.has_key(exp_data_db), "%s: Received unexpected message" %(self.__class__.__name__))

class addFlowSpace(Ping):
    def runTest(self):
        #Add flowspace
        flowspace_name = "dummyFlowName"
        flowspace_dpid = "1"
        flowspace_priority = 100
        flowspace_match = {"in_port" : 1, "dl_src" : "00:00:00:00:00:02"}
        flowspace_slice = [{"slice-name" : "controller0", "permission" : 7}]

        rule = ["add-flowspace" , flowspace_name, flowspace_dpid, flowspace_priority, flowspace_match, flowspace_slice, {}]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: AddFlowSpace: Not success" %(self.__class__.__name__))
        self.logger.info("Raw received " + str(data))

        #Check if flowspace added.
        rule = ["list-flowspace", {}]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        num_flow = len(data)
        self.logger.info("ListFlowSpace: Expected:     %s" %(testutils.NUM_FLOWSPACE_IN_CONF_FILE + 1))
        self.logger.info("ListFlowSpace: Received:     %s" % num_flow)
        self.logger.debug("ListFlowSpace: Raw received: %s" % data)
        self.assertEqual(num_flow, testutils.NUM_FLOWSPACE_IN_CONF_FILE + 1, "%s: Received wrong number of flow space" %(self.__class__.__name__))

        #Send packet across flowspace.
        pkt = testutils.simplePacket(dl_src="00:00:00:00:00:02")
        in_port = 1
        msg = testutils.genPacketIn(in_port=in_port, pkt=pkt)

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

class updateSlicePasswd(Ping):
    def runTest(self):
        new_passwd = "hello123"
        slice_user = "controller0"
        rule = ["update-slice-password", slice_user, new_passwd]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: UpdateSlicePasswd: Not success" %(self.__class__.__name__))
