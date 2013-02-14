"""
API (Delete Slice) test
It deletes slices from FlowVisor and make sure they are deleted
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
    basic_logger = logging.getLogger("del_slice")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------

class DelSlice(templatetest.TemplateTest):
    """
    Delete_slice and check the number of remaining slices
    It spawns flowvisor with two slices, spawns several switches,
    deletes both sclies and check the number of remaining slices
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Set up the test environment
        # -- Note: setting: config_file = test-base.xml, num of SW = 10, num of CTL = 0
        #                   no additional rules
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, num_of_switches=10, num_of_controllers=0)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

    def runTest(self):
        # Prepare slice deletion rules
        chk_slices = ["list-slices"]
        del_slice0 = ["remove-slice", "controller0"]
        del_slice1 = ["remove-slice", "controller1"]

        # Check initial number of slices. Should be three (two controllers + admin)
        (success, data) = testutils.setRule(self, self.sv, chk_slices)
        self.assertTrue(success, "%s: ListSlices: Not success" %(self.__class__.__name__))
        num_slice = len(data)
        self.logger.info("ListDevices: Expected:     " + str(3))
        self.logger.info("ListDevices: Received:     " + str(num_slice))
        self.logger.debug("ListDevices: Raw received: " + str(data))
        self.assertEqual(num_slice, 3, "%s: Received wrong number of slices" %(self.__class__.__name__))

        # Now delete slices
        (success, data) = testutils.setRule(self, self.sv, del_slice0)
        self.assertTrue(success, "%s: DeleteSlice: Not success" %(self.__class__.__name__))
        (success, data) = testutils.setRule(self, self.sv, del_slice1)
        self.assertTrue(success, "%s: DeleteSlice: Not success" %(self.__class__.__name__))

       # Check number of slices again. Should be one
        (success, data) = testutils.setRule(self, self.sv, chk_slices)
        self.assertTrue(success, "%s: ListSlices: Not success" %(self.__class__.__name__))
        num_slice = len(data)
        self.logger.info("ListDevices: Expected:     " + str(1))
        self.logger.info("ListDevices: Received:     " + str(num_slice))
        self.logger.debug("ListDevices: Raw received: " + str(data))
        self.assertEqual(num_slice, 1, "%s: Received wrong number of slices" %(self.__class__.__name__))
