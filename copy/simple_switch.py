# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An OpenFlow 1.0 L2 learning switch implementation.
"""

import logging
import struct

import sqlite3
from ryu.base import app_manager
from ryu.controller import mac_to_port
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.controller import dpset
from netaddr import *
from utils import *
from ryu.lib.mac import haddr_to_bin
'''
This file is edited from Ryu example which is located at  ryu/ryu/app/simple_switch.py.
According to its licecse(please don't trust my reading and read it), we can modify and use it as long as we keep the old license and state we've change the code. --Joe
'''

FLOW_HARD_TIMEOUT = 30
FLOW_IDLE_TIMEOUT = 10

class SimpleSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]
    
    servers = [0, [1, '10.10.1.1', '02:71:2a:55:7f:98'], [3, '10.10.1.2', '02:b4:9c:c8:84:42'], [4, '10.10.1.3', '02:51:94:52:e2:a7']]
    serverLoad = [0, 0, 0, 0]


    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    
    def add_flow(self, datapath, match, act, priority=0, idle_timeout=0, flags=0, cookie=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
   
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, actions=act, flags=flags, idle_timeout=idle_timeout, cookie=cookie)
        datapath.send_msg(mod)

    def forward_packet(self, msg, port_list):

        datapath = msg.datapath
        ofproto = datapath.ofproto

        actions = []
        
        for p in port_list:
            actions.append( createOFAction(datapath, ofproto.OFPAT_OUTPUT, p) )

        # install a flow to avoid packet_in next time
        if ofproto.OFPP_FLOOD not in port_list:
            match = getFullMatch( msg )
            sendFlowMod(msg, match, actions, FLOW_HARD_TIMEOUT, FLOW_IDLE_TIMEOUT, msg.buffer_id)
        else :

            sendPacketOut(msg=msg, actions=actions, buffer_id=msg.buffer_id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        dl_type_ipv4 = 0x0800
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        dst = eth.dst
        src = eth.src
	ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        dpid = datapath.id
	if ipv4_pkt:
           self.logger.info("packet in %s %s %s %s", dpid, ipv4_pkt.src, ipv4_pkt.dst, msg.in_port)
           match = parser.OFPMatch (dl_type = dl_type_ipv4, nw_src=self.ipv4_to_int(ipv4_pkt.src))
           serverID = 2 #scheduler()
           actions = [parser.OFPActionSetNwDst(self.ipv4_to_int(self.servers[serverID][1])), 
                    parser.OFPActionSetDlDst(haddr_to_bin(self.servers[serverID][2])), parser.OFPActionOutput(self.servers[serverID][0])]
           self.serverLoad[serverID]+=1
           self.add_flow(datapath, match, actions, 1, 10, ofproto.OFPFF_SEND_FLOW_REM, 2)
           self.logger.info("Flow installed for client %s and serverID %d", ipv4_pkt.src, serverID)
           actions = []
           actions.append( createOFAction(datapath, ofproto.OFPAT_OUTPUT, self.servers[serverID][0]) ) 
           sendPacketOut(msg=msg, actions=actions, buffer_id=msg.buffer_id)



	
	# if its ipv4_packet, install a flow with certain IDLE_TIME for the client to output to port N, given by the request to the scheduler.
	# Send the packet to that port. 

#	fd = os.open("/tmp/ryu/Distributed-Internet-Service-Delivery/controller.db", os.O_RDONLY)
#	conn = sqlite3.connect('/dev/fd/%d' % fd)
#	os.close(fd)
#        cursor = conn.cursor()
#        addressList = ('10.10.1.1', '10.10.1.2', '10.10.1.3') #filter client packets
#	pkt_arp = pkt.get_protocol(arp.arp)
#	if pkt_arp:
#         if pkt_arp.dst_ip in addressList: 
#	  print (pkt_arp)
#	  destination = (pkt_arp.dst_ip,) #get destination ip
#	  print (destination)
#	  cursor.execute("SELECT * from energyValues where id = (SELECT MAX(id) from energyValues where private_ip = ?)", destination)
#	  #	energyValue = cursor.fetchone()[1]
#	  recentInfo = cursor.fetchall()
#          print (recentInfo)
#	  print ("Energy value: " + str(recentInfo[0][1]))
#	  #	set.logger.info ("Last energy value: %s", str(energyValue))

#        self.macLearningHandle(msg)

#        out_port = self.get_out_port(msg)	

        #self.forward_packet(msg, [out_port])
    
    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removal_handler(self, ev):
        msg = ev.msg
        match = msg.match
	reason = msg.reason
        self.logger.info("Client released serverID = %d", msg.cookie)
	self.serverLoad[msg.cookie]-=1

    @set_ev_cls(dpset.EventDP, dpset.DPSET_EV_DISPATCHER)
    def _event_switch_enter_handler(self, ev):
       dl_type_ipv4 = 0x0800
       dl_type_arp = 0x0806
       dp = ev.dp
       ofproto = dp.ofproto
       parser = dp.ofproto_parser
       self.logger.info("Switch connected %s. Installing default flows...", dp)
       addressList = ('10.10.1.1', '10.10.1.2', '10.10.1.3') # process packets from servers normally
      # hwAddressList = ('02:71:2a:55:7f:98') #filter client packets
       actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
       for address in addressList:
         match = parser.OFPMatch(dl_type = dl_type_ipv4, nw_src = address)
         self.add_flow(dp, match, actions, 2, 0)     
#        self.logger.info("Added l2 flow for address %s", address)
       
       match = parser.OFPMatch(dl_type = dl_type_arp)#process arp packets normally
       self.add_flow(dp, match, actions, 1, 0)

      # match = parser.OFPMatch (dl_type = dl_type_ipv4, nw_src=self.ipv4_to_int('10.10.1.14'))
      # actions = [parser.OFPActionSetNwDst(self.ipv4_to_int(self.servers[2][1])), parser.OFPActionSetDlDst(haddr_to_bin(self.servers[2][2])), 
      # parser.OFPActionOutput(self.servers[2][0])]
       
      #self.serverLoad[2]+=1                                          
      # self.add_flow(dp, match, actions, 1, 10, ofproto.OFPFF_SEND_FLOW_REM, 2)
	
       match = parser.OFPMatch ()
       actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
       self.add_flow(dp, match, actions, 0, 0) #add miss flow
       self.logger.info("Added default rules for servers and miss-flow")

    def ipv4_to_int(self, string):
       	ip = string.split('.')
       	assert len(ip) == 4
       	i = 0
       	for b in ip:
    		b = int(b)
        	i = (i << 8) | b
        return i

