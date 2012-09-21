"""
Function test template
"""
import sys
import logging
import unittest
import testutils

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
    global basic_logger
    global basic_timeout
    global basic_config

    basic_logger = logging.getLogger("template")
    basic_logger.info("Initializing test set")
    basic_port_map = config["port_map"]
    basic_timeout = config["timeout"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


class TemplateTest(unittest.TestCase):
    """
    Root class for setting up the controller
    """

    def setUp(self):
        self.logger = basic_logger
        basic_logger.info("** START TEST CASE " + str(self))
        if basic_timeout == 0:
            self.timeout = None
        else:
            self.timeout = basic_timeout
        self.fv = None
        self.sv = None
        self.controllers = []
        self.switches = []

    def tearDown(self):
        #Tear down Fake controllers and switches
        testutils.tearDownFakeDevices(self)
        #Tear down FlowVisor if there is
        if self.fv:
            testutils.tearDownFlowVisor(self)
        else:
            basic_logger.info("FlowVisor is already gone")

        basic_logger.info("** END TEST CASE " + str(self))

    def runTest(self):
        pass

    def chkSetUpCondition(self, fv, sv_ret, ctl_ret, sw_ret):
        if self.fv == None:
            basic_logger.error("Could not bootup FlowVisor")
            self.tearDown()
            self.fail("Could not bootup FlowVisor")
        if sv_ret == False:
            basic_logger.error("Could not communicate with API server")
            self.tearDown()
            self.fail("Could not communicate with API server")
        if ctl_ret == False:
            basic_logger.error("Could not add controllers")
            self.tearDown()
            self.fail("Could not add controllers")
        if sw_ret == False:
            basic_logger.error("Could not add switches")
            self.tearDown()
            self.fail("Could not add switches")

if __name__ == '__main__':
    unittest.main()
