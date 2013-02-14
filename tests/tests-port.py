"""
Port status checking and port adding tests
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


class PktOutInport(templatetest.TemplateTest):
    """
    Packet_out to flood port with ingress port mentioned
    Check if FlowVisor expands the message so that it can exclude ingress_port
    from the message when it sends it to switch
    """
    def setUp(self):
        templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
        # Prepare additional rules to set
        # Set a rule in addition to a default config,
        # Now controller0 handles packets with specific dl_src from/to any ports
        rule1 = ["add-flowspace", "PktOutInportsetup", "all", 34000, 
            {"dl_src" : "00:11:22:33:44:55"}, 
            [{'slice-name' : 'controller0', 'permission' : 4 }], {} ]
        rule2 = ["list-flowspace", {} ]
        rules = [rule1, rule2]
        # Set up the test environment
        # -- Note: default setting: config_file = test-base.xml, num of SW = 1, num of CTL = 2
        (self.fv, self.sv, sv_ret, ctl_ret, sw_ret) = testutils.setUpTestEnv(self, fv_cmd=basic_fv_cmd, rules=rules)
        self.chkSetUpCondition(self.fv, sv_ret, ctl_ret, sw_ret)



    def runTest(self):
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src="00:11:22:33:44:55")
        pktout_ctl = testutils.genPacketOut(self, in_port=1, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [0,2,3] # Expect port1 to be excluded
        pktout_sw = testutils.genPacketOut(self, in_port=1, action_ports=ports_sw, pkt=pkt_ctl)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class AddPort(PktOutInport):
    """
    Port_status with adding a port
    When switch sends port_status with 'add port',
    check if controller which has all the switch ports can receive it
    while controller which has only specific ports cannot
    """
    def runTest(self):
        # Controller0 should be able to see the status change
        # but controller1 should not
        port13 = testutils.genPhyPort("port13", [00,0x13,0x44,0x66,0x88,0xaa], 13)
        msg = message.port_status()
        msg.reason = ofp.OFPPR_ADD
        msg.desc = port13

        snd_list = ["switch", 0, msg]
        exp_list = [["controller", 0, msg]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: PortStatus: Received unexpected message" %(self.__class__.__name__))

        # Ctl0 to sw packet_out_flood. Added port should be visible
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src="00:11:22:33:44:55")
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [0,1,2,3,13]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw, pkt=pkt_ctl)

        snd_list = ["controller", 0, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: PacketOut: Received unexpected message" %(self.__class__.__name__))

        # Ctl1 to sw packet_out_flood. Added port shouldn't be visible
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL1_0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [1,3]
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw, pkt=pkt_ctl)

        # Test
        snd_list = ["controller", 1, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: PacketOut: Received unexpected message" %(self.__class__.__name__))


class RmPortApi(PktOutInport):
    """
    ChangeFlowSpace with Remove via API
    Remove a port from flow space using API
    Check if the removed port is now invisible
    """
    def runTest(self):
        #for ctl1_id in ctl1_port1_ids:
        #    rule = ["changeFlowSpace", "REMOVE", ctl1_id]
        #    (success, data) = testutils.setRule(self, self.sv, rule)
        #    self.assertTrue(success, "%s: Not success" %(self.__class__.__name__))
        rule = ["remove-flowspace", "1006", "1007"]
        (success, data) = testutils.setRule(self, self.sv, rule)
        self.assertTrue(success, "%s: Not success" %(self.__class__.__name__)) 

        # Ctl1 to sw packet_out_flood. port1 now shouldn't be visible
        ports_ctl = [ofp.OFPP_FLOOD]
        pkt_ctl = testutils.simplePacket(dl_src=testutils.SRC_MAC_FOR_CTL1_0)
        pktout_ctl = testutils.genPacketOut(self, action_ports=ports_ctl, pkt=pkt_ctl)

        ports_sw = [3] # Expect port1 to be excluded
        pktout_sw = testutils.genPacketOut(self, action_ports=ports_sw, pkt=pkt_ctl)

        snd_list = ["controller", 1, 0, pktout_ctl]
        exp_list = [["switch", 0, pktout_sw]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)
        self.assertTrue(res, "%s: PacketOut: Received unexpected message" %(self.__class__.__name__))
