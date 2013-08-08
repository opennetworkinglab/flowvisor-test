"""
Tests for the configuration commands using fvconfig.
"""
import sys
import logging
import templatetest
import testutils
import oftest.cstruct as ofp
import oftest.message as message
import oftest.parse as parse
import oftest.action as action
import oftest.error as error
import socket
import time
import json
import subprocess
import threading
from pprint import pprint


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
    basic_logger = logging.getLogger("actions")
    basic_logger.info("Initializing test set")
    basic_timeout = config["timeout"]
    basic_port_map = config["port_map"]
    basic_config = config

# ------ End: Mandatory portion on each test case file ------

#Command class for calling the command.run which takes in a timeout period. 
#After the timeout period(usually reached when exceptions thrown), 
#the thread is stopped so that the test can continue on
class Command(object):
    def __init__(self, cmd):
	self.cmd = cmd
	self.process = None

    def run(self, timeout):
	def target():
      	    self.process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
 	    (out, err) = self.process.communicate()
	    basic_logger.debug("Received output: " + out)

	#Start thread with target as the command to be run.	
	thread = threading.Thread(target=target)
	thread.start()	

	#Wait for however long timeout is.	
	thread.join(timeout)
	if (thread.is_alive()):
	    basic_logger.debug("Terminating thread.")
	    self.process.terminate()
	    thread._Thread__stop()
	    #Takes too long, so return success value = False
	    return False
	#Command finished successfully, so success value = True
	else:
	    return True

class generateConfig(templatetest.TemplateTest):
    def setUp(self):
	templatetest.TemplateTest.setUp(self)
        self.logger = basic_logger
	return 

    def runTest(self):
	cmd = " generate "
	config_file = "newconfig.json"
	host_name = " host"
	host_passwd = " openflow"
	of_port = " 16633"
	api_port = " 6633"
	output = ""
	params = host_name +host_passwd + of_port + api_port
	
	#Generating newconfig.json
	self.logger.info("Running fvconfig" + cmd + config_file + params)
	command = Command("fvconfig" + cmd + config_file + params)
	success = command.run(timeout=10)
	self.assertTrue(success, "%s: Generate timeout" %(self.__class__.__name__))

	with open('newconfig.json') as data_file:
	     data = json.load(data_file)
	self.logger.debug("Data received: " + str(data))
	
	#Loading newconfig.json
	cmd = " load "
	self.logger.info("Running fvconfig" + cmd + config_file)
	command = Command("fvconfig" + cmd + config_file)
	success = command.run(timeout=10)
	self.assertTrue(success, "%s: Load timeout" %(self.__class__.__name__))

	#Loading DUMMYCONFIG.json. Should return error.
	config_file = "DUMMYCONFIG.json"
	self.logger.info("Running fvconfig" + cmd + config_file)
	command = Command("fvconfig" + cmd + config_file)
	success = command.run(timeout=10)
	self.assertFalse(success, "%s: Load error not caught." %(self.__class__.__name__))
	
	#Delete newconfig.json generated from this test.
	config_file = "newconfig.json"
	command = Command("rm -f " + config_file)
	success = command.run(timeout=10)
	self.assertTrue(success, "%s: rm Timeout." %(self.__class__.__name__))
