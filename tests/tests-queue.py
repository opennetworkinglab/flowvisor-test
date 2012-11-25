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
                    dl_dst = "00:00:00:00:00:00", queue_id = 1, outport = 0, is_queue=True):

    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst=dl_dst, dl_type=0, dl_vlan=0, tp_src=0,tp_dst=0)

    enqueue = action.action_enqueue()
    enqueue.queue_id = queue_id
    enqueue.port = outport

    output = action.action_output()
    output.port = outport

    if is_queue:
        action_list = [enqueue]
    else:
        action_list = [output]

    flow_mod = testutils.genFloModFromPkt(parent, pkt, ing_port=0, action_list=action_list)
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



class EnqueueQueue(EnqueueNoQueue):

 
    """
    Enqueue Action
    Check is enqueue action is passed if the queue_id is
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



class EnqueueForce(EnqueueNoQueue):

 
    """
    Enqueue Action
    If the flowspace entries forces a queue
    then check that the output action is replaced
    by the enqueue action.
    """
    def runTest(self):


        rule = ["changeFlowSpace", "ADD", "31000", "all", "in_port=0,dl_src=00:00:00:00:00:03,queues=1,force_enqueue=1", "Slice:controller0=4"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__)) 

        flowmod_enqueue_action = _genFlowModEnqueue(self, dl_src="00:00:00:00:00:03")
        flowmod_output_action = _genFlowModEnqueue(self, dl_src="00:00:00:00:00:03", is_queue=False)
        
        snd_list = ["controller", 0, 0, flowmod_output_action]
        exp_list = [ ["switch", 0, flowmod_enqueue_action] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : FlowModEnqueue: Received unexepected message" % (self.__class__.__name__))


        rule = ["changeFlowSpace", "ADD", "31000", "all", "in_port=0,dl_src=00:00:00:00:00:04,queues=1:2:3,force_enqueue=1", "Slice:controller0=4"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__)) 

        flowmod_enqueue_action = _genFlowModEnqueue(self, dl_src="00:00:00:00:00:04")
        flowmod_output_action = _genFlowModEnqueue(self, dl_src="00:00:00:00:00:04", is_queue=False)
        
        snd_list = ["controller", 0, 0, flowmod_output_action]
        exp_list = [ ["switch", 0, flowmod_enqueue_action] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : FlowModEnqueue: Received unexepected message" % (self.__class__.__name__))


class QueueConfig(EnqueueNoQueue):
    """
    Push QueueConfigRequest, if for a port that is not
    in the slice verify we get an error. If for a port
    that is in the slice check we get a reply appropriately
    pruned by the queues defined in the slice
    """
    
    def runTest(self):
        rule = ["changeFlowSpace", "ADD", "31000", "all", "in_port=0,dl_src=00:00:00:00:00:03,queues=1,force_enqueue=1", "Slice:controller0=4"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))

        qconfreq = message.queue_get_config_request()
        qconfreq.port = 1

        err = error.bad_request_error_msg()
        err.xid = 0
        err.code = ofp.OFPBRC_EPERM        
        err.data = qconfreq.pack()

        snd_list = ["controller", 0, 0, qconfreq]
        exp_list = [ ["controller", 0, err] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, hdr_only=True)
        self.assertTrue(res, "%s : QueueConfigRequestBadPort: Received unexepected message" % (self.__class__.__name__))

        qconfreq.port = 0
        snd_list = ["controller", 0, 0, qconfreq]
        exp_list = [ ["switch", 0, qconfreq] ]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : QueueConfigGoodPort: Received unexepected message" % (self.__class__.__name__))


        qconfrep = message.queue_get_config_reply()
        qconfrep.header.xid = ret_xid
        qconfrep.port = 0
        q1 = message.packet_queue()
        q1.queue_id = 0
        
        
        prop = ofp.ofp_queue_prop_header()
        q1.properties = [prop]

        qconfrep.queues = [q1] 

        snd_list = ["switch", 0, qconfrep]
        exp_list = [ ["controller", 0, None] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : QueueConfigReply1: Received unexepected message" % (self.__class__.__name__))
        
        q2 = ofp.ofp_packet_queue()
        q2.queue_id = 1
        qconfrep.queues = [q1, q2]
        q2.properties = [prop]
#
        prunedqconf = message.queue_get_config_reply()
        prunedqconf.header.xid = ret_xid
        prunedqconf.port = 0
        prunedqconf.queues = [q2] 

        snd_list = ["switch", 0, qconfrep]
        exp_list = [ ["controller", 0, prunedqconf] ]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s : QueueConfigReply2 Received unexepected message" % (self.__class__.__name__))
         

