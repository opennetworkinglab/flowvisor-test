"""
API tests
It sends and receives API commands to/from FlowVisor and verify them
"""

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
        ping_str = "FlowVisor Test"
        rule = ["ping", ping_str]
        exp_data1 = "PONG\(fvadmin\):"
        exp_data2 = ping_str
        # send the command and expect to receive pong
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        self.logger.info("Ping: Expected: " + exp_data1)
        self.logger.info("Ping: Expected: " + exp_data2)
        self.logger.info("Ping: Received: " + data)
        self.assertTrue(re.search(exp_data1,data), "%s: Received unexpected message" %(self.__class__.__name__))
        self.assertTrue(re.search(exp_data2,data), "%s: Received unexpected message" %(self.__class__.__name__))


class ListFlowSpace(Ping):
    """
    List_flow_space and response
    Check if FlowVisor receives listFlowSpace from API client and sends back
    the correct response
    """
    def runTest(self):
        rule = ["listFlowSpace"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        num_flow = len(data)
        self.logger.info("ListFlowSpace: Expected:     " + str(testutils.NUM_FLOWSPACE_IN_CONF_FILE))
        self.logger.info("ListFlowSpace: Received:     " + str(num_flow))
        self.logger.debug("ListFlowSpace: Raw received: " + str(data))
        self.assertEqual(num_flow, testutils.NUM_FLOWSPACE_IN_CONF_FILE, "%s: Received wrong number of flow space" %(self.__class__.__name__))


class ListDevices(Ping):
    """
    List_devices and response
    Check if FlowVisor receives listDevices from API client and sends back
    the correct response
    """
    def runTest(self):
        rule = ["listDevices"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        num_dev = len(data)
        self.logger.info("ListDevices: Expected:     " + str(NUM_SW))
        self.logger.info("ListDevices: Received:     " + str(num_dev))
        self.logger.debug("ListDevices: Raw received: " + str(data))
        self.assertEqual(num_dev, NUM_SW, "%s: Received wrong number of switches" %(self.__class__.__name__))


class GetLinks(Ping):
    """
    Get_links and response
    Check if FlowVisor receives getLinks from API client and sends back
    the correct number of links
    """
    def runTest(self):
        rule = ["getLinks"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        num_link = len(data)
        self.logger.info("GetLinks: Expected:     " + str(testutils.NUM_LINK_IN_CONF_FILE))
        self.logger.info("GetLinks: Received:     " + str(num_link))
        self.logger.debug("GetLinks: Raw received: " + str(data))
        self.assertEqual(num_link, testutils.NUM_LINK_IN_CONF_FILE, "%s: Received wrong number of switches" %(self.__class__.__name__))


class ChangeFlowSpace(Ping):
    """
    Change_flow_space and response
    Check if FlowVisor receives changeFlowSpace from API client without error
    """
    def runTest(self):
        rule = ["changeFlowSpace", "REMOVE", testutils.EXIST_ID_IN_CONF_FILE]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))


class CreateSlice(Ping):
    """
    Create_slice and verify
    Check if FlowVisor receives and performs createSlice
    Check FlowVisor refuses to create/change it when illegal conditions
    """
    def runTest(self):
        # createSlice
        slice_name = "controller2"
        slice_pswd = "ctl2pass"
        slice_port = "tcp:localhost:54323"
        slice_email = "ctl2@foo.com"
        rule = ["createSlice", slice_name, slice_pswd, slice_port, slice_email]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: CreateSlice: Not success" %(self.__class__.__name__))

        # check if it has been created
        rule = ["getSliceInfo", "controller2"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: GetSliceInfo: Not success" %(self.__class__.__name__))
        num_data = len(data)
        self.assertTrue(len(data)>0, "%s: Slice Creation Failed" %(self.__class__.__name__))
        self.assertTrue(data.has_key('contact_email'), "%s: No contact_email" %(self.__class__.__name__))
        self.logger.info("CreateSlice: Expected:     " + slice_email)
        self.logger.info("CreateSlice: Received:     " + data.get('contact_email'))
        self.logger.debug("CreateSlice: Raw received: " + str(data))
        # this data is a list
        self.assertEqual(data.get('contact_email'), slice_email, "%s: Received wrong slice_email" %(self.__class__.__name__))

        # Try to create a slice with a same name and different configuration.
        # Should be failed
        slice_random_email = "ctl2@bar.com"
        rule = ["createSlice", slice_name, slice_pswd, slice_port, slice_random_email]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertFalse(success, "%s: Shouldn't be created" %(self.__class__.__name__))

        # As of FV0.9, Slice with fieldseparator is allowed.
        # Should be accepted
        slice_name = "contro!ler3"
        slice_pswd = "ctl3pass"
        slice_port = "tcp:localhost:54324"
        slice_email = "ctl3@foo.com"
        rule = ["createSlice", slice_name, slice_pswd, slice_port, slice_email]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: The slice should be created" %(self.__class__.__name__))



class DeleteSlice(Ping):
    """
    Delete_slice
    Check if FlowVisor receives createSlice and check it is deleted
    with counting the number of slices using listFlowSpace
    """
    def runTest(self):
        # Try to delete controller0
        rule = ["deleteSlice", testutils.EXIST_SLICE0_IN_CONF_FILE]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: DeleteSlice: Not success" %(self.__class__.__name__))

        remaining_fs = testutils.NUM_FLOWSPACE_IN_CONF_FILE-testutils.NUM_FLOWSPACE_EXIST_SLICE0
        # Check number of flow space
        rule = ["listFlowSpace"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: ListFlowSpace: Not success" %(self.__class__.__name__))

        num_flow = len(data)
        self.logger.info("ListFlowSpace: Expected:     " + str(remaining_fs))
        self.logger.info("ListFlowSpace: Received:     " + str(num_flow))
        self.logger.debug("ListFlowSpace: Raw received: " + str(data))
        self.assertEqual(num_flow, remaining_fs, "%s: Received wrong number of flow space" %(self.__class__.__name__))


class SliceOwner(Ping):
    """
    API command exchange as a slice owner
    Check if API client can connect with FlowVisor as a slice owner
    Perform flow_space related commands and verify the response
    """
    def runTest(self):
        # parameters: excerpt from config file
        slice_user = "controller1"
        slice_pswd = "bobPass"
        slice_port = 54322
        num_flowspace_ctl1 = 4

        # Spawn API client for controller1
        sv_ctl1 = testutils.spawnApiClient(self, slice_user, slice_pswd)

        # ping
        ping_str = "Controller1 Test"
        rule = ["ping", ping_str]
        exp_data1 = "PONG\(controller1\):"
        exp_data2 = ping_str
        # send the command and expect to receive pong
        (success, data) = testutils.setRule(self, sv_ctl1, rule)
        self.assertTrue(success, "%s: Ping: Not success" %(self.__class__.__name__))
        self.logger.info("Ping: Expected: " + exp_data1)
        self.logger.info("Ping: Expected: " + exp_data2)
        self.logger.info("Ping: Received: " + data)
        self.assertTrue(re.search(exp_data1,data), "%s: Received unexpected message" %(self.__class__.__name__))
        self.assertTrue(re.search(exp_data2,data), "%s: Received unexpected message" %(self.__class__.__name__))

        # listFlowSpace
        rule = ["listFlowSpace"]
        (success, data) = testutils.setRule(self, sv_ctl1, rule)
        self.assertTrue(success, "%s: ListFlowSpace: Not success" %(self.__class__.__name__))
        num_flow = len(data)
        self.logger.info("ListFlowSpace: Expected:     " + str(num_flowspace_ctl1))
        self.logger.info("ListFlowSpace: Received:     " + str(num_flow))
        self.logger.debug("ListFlowSpace: Raw received: " + str(data))
        self.assertEqual(num_flow, num_flowspace_ctl1, "%s: Received wrong number of flow space" %(self.__class__.__name__))

        # changeSlice
        # change email
        new_email = "controller1new@new.com"
        rule = ["changeSlice", slice_user, "contact_email", new_email]
        (success, data) = testutils.setRule(self, sv_ctl1, rule)
        self.assertTrue(success, "%s: ChangeSlice: Not success" %(self.__class__.__name__))

        # changeSlice
        # change port
        new_port = "44444"
        rule = ["changeSlice", slice_user, "controller_port", new_port]
        (success, data) = testutils.setRule(self, sv_ctl1, rule)
        self.assertTrue(success, "%s: ChangeSlice: Not success" %(self.__class__.__name__))

        # getSliceInfo
        # Check email and port above have been set
        rule = ["getSliceInfo", slice_user]
        (success, data) = testutils.setRule(self, sv_ctl1, rule)
        self.assertTrue(success, "%s: GetSliceInfo: Not success" %(self.__class__.__name__))
        # The response is a dictionary
        # It should contain "contact_name" and "controller_port"
        self.logger.info("GetSliceInfo: Expected:     " + new_email)
        self.logger.info("GetSliceInfo: Received:     " + data['contact_email'])
        self.logger.info("GetSliceInfo: Expected:     " + new_port)
        self.logger.info("GetSliceInfo: Received:     " + data['controller_port'])
        self.logger.debug("GetSliceInfo: Raw received: " + str(data))
        self.assertEqual(data['contact_email'], new_email, "%s: Received unexpected contact_email" %(self.__class__.__name__))
        self.assertEqual(data['controller_port'], new_port, "%s: Received unexpected controller_port" %(self.__class__.__name__))
