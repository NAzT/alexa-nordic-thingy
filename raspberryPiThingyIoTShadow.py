'''
/*
 * Copyright 2010-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *  http://aws.amazon.com/apache2.0
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
 '''

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
import logging
import time
import json
import argparse

from bluepy import btle, thingy52
import binascii


# Shadow JSON schema:
#
# Name: Bot
# {
#	"state": {
#		"desired":{
#			"property":<INT VALUE>
#		}
#	}
# }


# Create struct that will be used to store Thingy Sensor Data
class Thingy52SensorData:
    def __init__(self):
        self.temperature = 0

thingy52Data = Thingy52SensorData()
thingShadowData = Thingy52SensorData()


# Custom Shadow callback
def customShadowCallback_Delta(payload, responseStatus, token):
    # payload is a JSON string ready to be parsed using json.loads(...)
    # in both Py2.x and Py3.x
    print(responseStatus)
    payloadDict = json.loads(payload)
    print(payloadDict)

    # When we receive Delta message from IoT Thing, we use this as a request later on
    # TBD
    print("++++++++DELTA++++++++++")
    print("temperature: " + str(payloadDict["state"]["temperature"]))
    print("version: " + str(payloadDict["version"]))
    print("+++++++++++++++++++++++\n\n")

# Custom Shadow callback
def customShadowCallback_Update(payload, responseStatus, token):
    # payload is a JSON string ready to be parsed using json.loads(...)
    # in both Py2.x and Py3.x
    if responseStatus == "timeout":
        print("Update request " + token + " time out!")
    if responseStatus == "accepted":
        payloadDict = json.loads(payload)

        # Print out status message on reported temperature entry. If temperature does not exist, this will fail
        print("# ~~~~~~~~~~~~~~~~~~~~~~~")
        print("# Update request with token: " + token + " accepted!")
        print("# temperature: " + str(payloadDict["state"]["reported"]["temperature"]))
        print("# ~~~~~~~~~~~~~~~~~~~~~~~\n\n")

        # Update shadow struct with new reported data
        print("# Update local shadow variable to store new reported value")
        thingShadowData.temperature = int(payloadDict["state"]["reported"]["temperature"])
        
    if responseStatus == "rejected":
        print("Update request " + token + " rejected!")


# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
parser.add_argument("-n", "--thingName", action="store", dest="thingName", default="Bot", help="Targeted thing name")
parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicShadowDeltaListener",
                    help="Targeted client id")
parser.add_argument("-m", "--macaddress", action="store", dest="thingyMacAddress", default="xx:XX:xx:XX:xx:XX",
                    help="Mac address of your Thingy")

args = parser.parse_args()
host = args.host
rootCAPath = args.rootCAPath
certificatePath = args.certificatePath
privateKeyPath = args.privateKeyPath
thingName = args.thingName
clientId = args.clientId

if (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

if args.thingyMacAddress == "xx:XX:xx:XX:xx:XX":
    parser.error("Missing MAC address of Thingy device to connect to.")
    exit(2)

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTShadowClient = None
myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient(clientId)
myAWSIoTMQTTShadowClient.configureEndpoint(host, 8883)
myAWSIoTMQTTShadowClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTShadowClient configuration
myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect to AWS IoT
myAWSIoTMQTTShadowClient.connect()

# Create a deviceShadow with persistent subscription
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName(thingName, True)

# Listen on deltas
deviceShadowHandler.shadowRegisterDeltaCallback(customShadowCallback_Delta)



# Create notification handlers and establish connection to Nordic Thingy:52
def str_to_int(s):
    """ Transform hex str into int. """
    i = int(s, 16)
    if i >= 2**7:
        i -= 2**8
    return i

class NewDelegate(btle.DefaultDelegate):
    def handleNotification(self, hnd, data):
        if (hnd == thingy52.e_temperature_handle):
            teptep = binascii.b2a_hex(data)
            thingy52Data.temperature = str_to_int(teptep[:-2])
            print('Notification: Temp received:  {}.{} degCelcius'.format(
                        thingy52Data.temperature, int(teptep[-2:], 16)))
            
        if (hnd == thingy52.ui_button_handle):
            print("# Notification: Thingy Button press received: {}".format(repr(data)))

print("# Connecting to Thingy with address {}...".format(args.thingyMacAddress))
thingy = thingy52.Thingy52(args.thingyMacAddress)

print("# Setting notification handler to new handler...")
thingy.setDelegate(NewDelegate())

print("# Configuring and enabling temperature notification...")
thingy.environment.enable()
thingy.environment.configure(temp_int=5000) # 5000 means 5 seconds
thingy.environment.set_temperature_notification(True)

print("# Configuring and enabling button press notification...")
thingy.ui.enable()
thingy.ui.set_btn_notification(True)


# Loop forever
while True:

    # Sleep for xx.x seconds before checking if data has changed unless notification arrives
    print("# Waiting for notification with timeout enabled...")
    thingy.waitForNotifications(timeout=10.0)

    if thingShadowData.temperature != thingy52Data.temperature:
        print("# Update IoT Thing reported temperature to be the collected one {} from current {}...".format(
                    thingy52Data.temperature, thingShadowData.temperature))
        JSONPayload = '{"state":{"reported":{"temperature": "%d"}}}' % thingy52Data.temperature
        deviceShadowHandler.shadowUpdate(JSONPayload, customShadowCallback_Update, 5)
        # Update shadow data in the callback when we know if it was accepted or not
    

# Will never be called because of the while True loop
print("# Disconnecting...")
thingy.disconnect()    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    