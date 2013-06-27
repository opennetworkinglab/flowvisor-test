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

PACKET_COUNT=10
DURATION_SEC=100
DURATION_NSEC=10000000
BYTE_COUNT=640

def _genFlowModArp(parent, wildcards=0x3ffffa, dl_src = testutils.SRC_MAC_FOR_CTL0_0, 
		dl_dst="00:00:00:00:00:00", out_ports=[0], in_port=0):
    """
    Create flow_mod with arp matching that matches controller0 using given limited parameters
    Other parameters are chosen at random
    """
    pkt = testutils.simplePacket(dl_src=dl_src, dl_dst=dl_dst, dl_type=0, dl_vlan=0, tp_src=0,tp_dst=0)

    action_list = []
    for port in out_ports:
        act = action.action_output()
        act.port = port
        action_list.append(act)
    flow_mod = testutils.genFloModFromPkt(parent, pkt, ing_port=in_port, action_list=action_list)
    flow_mod.match.wildcards = wildcards
    return flow_mod

def _genFlowStatssEntry(table_id=1, match=None, cookie=0, actions=None):
    entry = message.flow_stats_entry()
    entry.table_id = table_id
    entry.match = match
    entry.duration_sec = DURATION_SEC
    entry.duration_nsec = DURATION_NSEC
    entry.cookie = cookie
    entry.packet_count = PACKET_COUNT
    entry.byte_count = BYTE_COUNT
    if actions is not None:
        entry.actions = actions
    return entry


def _genAllAggsStats():
    match = ofp.ofp_match()
    match.wildcards = ofp.OFPFW_ALL
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

    msg = message.aggregate_stats_request()
    msg.header.xid = testutils.genVal32bit()
    msg.match = match
    msg.table_id = 0xff
    msg.out_port = 0xffff
    return msg




def _genAllFlowsStats():
    match = ofp.ofp_match()
    match.wildcards = ofp.OFPFW_ALL
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
    return msg


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
        fm1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        fm2 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])
        fm3 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:01",out_ports=[3], in_port=1) 
	
        cookie = []
        snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm1 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm2 = cookie[0]

        cookie = []
        snd_list = ["controller", 1, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm3 = cookie[0]

        msg = _genAllFlowsStats()

        cookie = []
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

	
        fsr = message.flow_stats_reply()
        fsr.header.xid = ret_xid
        fsr_cont = message.flow_stats_reply()
        entry1 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=cookie_fm1)
        entry11 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=0)
        entry2 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=cookie_fm2)
        entry22 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=0)
        entry3 = _genFlowStatssEntry(table_id=1, match=fm3.match, cookie=cookie_fm3)


        fsr.stats = [entry1, entry2, entry3]
        fsr_cont.stats = [entry11, entry22]
		
        snd_list = ["switch", 0, fsr]
        exp_list = [["controller", 0, fsr_cont]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)  
        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))


class FlowStatFragments(templatetest.TemplateTest):
    """
    FlowStatFragments checking after deleting slices
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
        fm1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        fm2 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])
        fm3 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:01",out_ports=[3], in_port=1)

        cookie = []
        snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm1 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm2 = cookie[0]

        cookie = []
        snd_list = ["controller", 1, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm3 = cookie[0]

        msg = _genAllFlowsStats()

        cookie = []
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, msg]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))
        
        fsr_cont = message.flow_stats_reply()
        fsr_cont.flags = 1    


        fsr = message.flow_stats_reply()
        fsr.header.xid = ret_xid
        entry1 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=cookie_fm1)
        fsr.flags = 1
        
        fsr.stats = [entry1]

        snd_list = ["switch",0,fsr]
        
        entry11 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=0)
        #fsr_cont.stats = [entry11]
        #exp_list = [["controller", 0, fsr_cont]]
        
        """
        fsr_cont.stats = []
        exp_list = [["controller", 0, fsr_cont]]
        """
        
        res = testutils.ofmsgSndCmpWithXid(self, snd_list, [["controller", 0, None]] , xid_ignore=True)

        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))
        
        fsr2 = message.flow_stats_reply()
        fsr2.header.xid = fsr.header.xid
        entry2 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=cookie_fm2)
        #fsr2 = fsr
        fsr2.flags = 0
        
        fsr2.stats = [entry2]

        snd_list = ["switch",0,fsr2]
        """
        #fsr3 = message.flow_stats_reply()
        #fsr3.header.xid = ret_xid
        #entry3 = _genFlowStatssEntry(table_id=1, match=fm3.match, cookie=cookie_fm3)
        #fsr3.flags = 0
        
        #fsr3.stats = [entry3]

        #fsr.stats = [entry1, entry2, entry3]

        #snd_list = ["switch",0,fsr]
        """

        entry22 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=0)
        fsr_cont.flags = 0
        fsr_cont.stats = [entry11, entry22]
        #fsr_cont.stats = [entry22]
        exp_list = [["controller", 0, fsr_cont]]

        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)

        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))





	
class FlowStatsSpecific(FlowStats):
    """
    User request a specific flow entry as stats
    With and without outport
    """

    def runTest(self):
         # Matching field values below are from original regression test case
        fm1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        fm2 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])
        fm3 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:01",out_ports=[3], in_port=1) 
        fm4 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[3])        
	
        cookie = []
        snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm1 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm2 = cookie[0]

        cookie = []
        snd_list = ["controller", 1, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm3 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm4]
        exp_list = [["switch", 0, fm4]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm4 = cookie[0]



        match = ofp.ofp_match()
        match.wildcards = 4194298
        match.in_port = 0
        match.dl_dst = parse.parse_mac("00:00:00:00:00:00")
        match.dl_src = parse.parse_mac("00:00:00:00:00:02")
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
        exp_list = [["switch", 0, _genAllFlowsStats()]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

	
        fsr = message.flow_stats_reply()
        fsr.header.xid = ret_xid
        fsr_cont = message.flow_stats_reply()
        entry1 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=cookie_fm1, actions=fm1.actions)
        entry2 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=cookie_fm2, actions=fm2.actions)
        entry3 = _genFlowStatssEntry(table_id=1, match=fm3.match, cookie=cookie_fm3, actions=fm3.actions)
        entry4 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=cookie_fm4, actions=fm4.actions)



        entry11 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=0, actions=fm1.actions)
        entry44 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=0, actions=fm4.actions)
        fsr.stats = [entry1,entry2,entry3, entry4]
        fsr_cont.stats = [entry11,entry44]
       
        snd_list = ["switch", 0, fsr]
        exp_list = [["controller", 0, fsr_cont]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)  
        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))

        """
        change flowstats request to match on outport: 3
        """
        msg.xid = testutils.genVal32bit()  
        msg.out_port = 3
        fsr_cont.stats = [entry44]


        # should return straight to controller because we are rate limiting flowstats request.
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, fsr_cont]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


class AggStats(FlowStats):


    def runTest(self):
         # Matching field values below are from original regression test case
        fm1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        fm2 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])
        fm3 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:01",out_ports=[3], in_port=1) 
        fm4 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[3])        
	
        cookie = []
        snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm1 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm2 = cookie[0]

        cookie = []
        snd_list = ["controller", 1, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm3 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm4]
        exp_list = [["switch", 0, fm4]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm4 = cookie[0]

        snd_list = ["controller", 0, 0, _genAllAggsStats()]
        exp_list = [["switch", 0, _genAllFlowsStats()]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))


        fsr = message.flow_stats_reply()
        fsr.header.xid = ret_xid
        entry1 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=cookie_fm1, actions=fm1.actions)
        entry2 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=cookie_fm2, actions=fm2.actions)
        entry3 = _genFlowStatssEntry(table_id=1, match=fm3.match, cookie=cookie_fm3, actions=fm3.actions)
        entry4 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=cookie_fm4, actions=fm4.actions)

        entry11 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=0, actions=fm1.actions)
        entry44 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=0, actions=fm4.actions)
        fsr.stats = [entry1,entry2,entry3, entry4]

        asr = message.aggregate_stats_reply()
        asr.header.xid = ret_xid
        entry = message.aggregate_stats_entry()
        
        entry.packet_count = 3 * PACKET_COUNT
        entry.byte_count = 3 * BYTE_COUNT
        entry.flow_count = 3

        asr.stats = [entry]
       
        snd_list = ["switch", 0, fsr]
        exp_list = [["controller", 0, asr]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)  
        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))


class AggStatsSpecific(AggStats):

     def runTest(self):
         # Matching field values below are from original regression test case
        fm1 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[2])
        fm2 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:01:00:00:00:02",out_ports=[2])
        fm3 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:01",out_ports=[3], in_port=1) 
        fm4 = _genFlowModArp(self,wildcards=0x3ffffa,dl_src="00:00:00:00:00:02",out_ports=[3])        
	
        cookie = []
        snd_list = ["controller", 0, 0, fm1]
        exp_list = [["switch", 0, fm1]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm1 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm2]
        exp_list = [["switch", 0, fm2]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm2 = cookie[0]

        cookie = []
        snd_list = ["controller", 1, 0, fm3]
        exp_list = [["switch", 0, fm3]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm3 = cookie[0]

        cookie = []
        snd_list = ["controller", 0, 0, fm4]
        exp_list = [["switch", 0, fm4]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True, cookies=cookie)
        self.assertTrue(res, "%s: FlowMod_Expand: Received unexpected message" %(self.__class__.__name__))
        cookie_fm4 = cookie[0]



        match = ofp.ofp_match()
        match.wildcards = 4194298
        match.in_port = 0
        match.dl_dst = parse.parse_mac("00:00:00:00:00:00")
        match.dl_src = parse.parse_mac("00:00:00:00:00:02")
        match.dl_type = 0
        match.dl_vlan = 0
        match.dl_vlan_pcp = 0
        match.nw_src = parse.parse_ip("0.0.0.0")
        match.nw_dst = parse.parse_ip("0.0.0.0")
        match.nw_tos = 0
        match.nw_proto = 0
        match.tp_src = 0
        match.tp_dst = 0

        msg = message.aggregate_stats_request()
        msg.header.xid = testutils.genVal32bit()
        msg.match = match
        msg.table_id = 0xff
        msg.out_port = 0xffff

        snd_list = ["controller", 0, 0, msg]
        exp_list = [["switch", 0, _genAllFlowsStats()]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

	
        fsr = message.flow_stats_reply()
        fsr.header.xid = ret_xid
        entry1 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=cookie_fm1, actions=fm1.actions)
        entry2 = _genFlowStatssEntry(table_id=1, match=fm2.match, cookie=cookie_fm2, actions=fm2.actions)
        entry3 = _genFlowStatssEntry(table_id=1, match=fm3.match, cookie=cookie_fm3, actions=fm3.actions)
        entry4 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=cookie_fm4, actions=fm4.actions)



        entry11 = _genFlowStatssEntry(table_id=1, match=fm1.match, cookie=0, actions=fm1.actions)
        entry44 = _genFlowStatssEntry(table_id=1, match=fm4.match, cookie=0, actions=fm4.actions)
        fsr.stats = [entry1,entry2,entry3, entry4]

        asr = message.aggregate_stats_reply()
        asr.header.xid = ret_xid
        entry = message.aggregate_stats_entry()
        
        entry.packet_count = 2 * PACKET_COUNT
        entry.byte_count = 2 * BYTE_COUNT
        entry.flow_count = 2

        asr.stats = [entry]
       
        snd_list = ["switch", 0, fsr]
        exp_list = [["controller", 0, asr]]
        res = testutils.ofmsgSndCmp(self, snd_list, exp_list, xid_ignore=True)  
        self.assertTrue(res, "%s: flowstats: Received unexpected message" %(self.__class__.__name__))

        """
        change flowstats request to match on outport: 3
        """
        msg.xid = testutils.genVal32bit()  
        msg.out_port = 3
        entry.packet_count = PACKET_COUNT
        entry.byte_count = BYTE_COUNT
        entry.flow_count = 1
        asr.stats = [entry]


        # should return straight to controller because we are rate limiting flowstats request.
        snd_list = ["controller", 0, 0, msg]
        exp_list = [["controller", 0, asr]]
        (res, ret_xid) = testutils.ofmsgSndCmpWithXid(self, snd_list, exp_list, xid_ignore = True)
        self.assertTrue(res, "%s: Received unexpected message" %(self.__class__.__name__))

   
