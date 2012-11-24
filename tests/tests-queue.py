"""
Simple tests exchanging OFprotocol btwn sw and ctl via FV
"""

import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
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
    basic_logger = logging.getLogger("basic")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------


def _genFlowModEnqueue(parent, wildcards=0x3ffffa, dl_src = testutils.SRC_MAC_FOR_CTL0_0, \
                    dl_dst = "00:00:00:00:00:00", queue_id = 1, outport = 0):

    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst=dl_dst, dl_type=0, dl_vlan=0, tp_src=0,tp_dst=0)

    enqueue = action.action_enqueue()
    enqueue.queue_id = queue_id
    enqueue.port = outport

    flow_mod = testutils.genFloModFromPkt(parent, pkt, ing_port=0, action_list=[enqueue])
    flow_mod.match.wildcards = wildcards 

    return flow_mod

class EnqueueNoQueue(templatetest.TemplateTest):

    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, \
            num_of_switches=2, num_of_controllers=2)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

 
    """
    Enqueue Action
    Check is enqueue action is rejected if the queue_id is not
    in the slice.
    """
    def runTest(self):

        flowmod = _genFlowModEnqueue(self)
        
        
        #generate error
        err = error.bad_action_error_msg()
        err.header.xid = 0
        err.code = ofp.OFPBAC_BAD_QUEUE
        err.data = flowmod.pack()

        #send queue
        #recv error
        snd_list = ["controller", 0, 0, flowmod]
        exp_list = [ ["controller", 0, err] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, hdr_only=True)
        self.assertTrue(res, "%s : FlowModEnqueue: Received unexepected message" % (self.__class__.__name__))



class EnqueueQueue(templatetest.TemplateTest):

    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, \
            num_of_switches=2, num_of_controllers=2)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)

 
    """
    Enqueue Action
    Check is enqueue action is rejected if the queue_id is not
    in the slice.
    """
    def runTest(self):


        rule = ["changeFlowSpace", "ADD", "33000", "all", "in_port=0,dl_src=00:00:00:00:00:02,queues=1", "Slice:controller0=4"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__)) 

        flowmod = _genFlowModEnqueue(self)
        
        snd_list = ["controller", 0, 0, flowmod]
        exp_list = [ ["switch", 0, flowmod] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : FlowModEnqueue: Received unexepected message" % (self.__class__.__name__))

