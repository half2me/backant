import json
import random
import socket
import sys
from threading import Lock, Thread, Event

import zmq
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from libAnt.drivers.pcap import PcapDriver
from libAnt.node import Node
from libAnt.profiles.factory import Factory as AntFactory
from twisted.internet import reactor
from twisted.python import log

config = { # default values
    "bikeId": 0,
    "webSocketPort": 9000,
    "meshPort": 9999,
    "meshBufferSize": 5000
}

# Parse config values
try:
    with open("settings.txt", 'r') as file:
        for line in file:
            key, value = line.strip('"\n').split('=')
            config[key] = value
except FileNotFoundError as e:
    print (e)

def synchronized(method):
    """ Work with instance method only !!! """
    def new_method(self, *arg, **kws):
        with self.lock:
            return method(self, *arg, **kws)
    return new_method

class meshLoop(Thread):
    def __init__(self, socket, callback):
        super().__init__()
        self.sock = socket
        self.callback = callback
        self.poller = zmq.Poller()
        self.poller.register(self.sock, zmq.POLLIN)
        self.stopper = Event()

    def stop(self):
        self.stopper.set()

    def run(self):
        while not self.stopper.isSet():
            events = dict(self.poller.poll(1))
            if self.sock.fileno() in events:
                msg, addrinfo = self.sock.recvfrom(config["meshBufferSize"])
                try:
                    self.callback(msg)
                except Exception as e:
                    print(e)

class MyServerProtocol(WebSocketServerProtocol):

    def __init__(self):
        super().__init__()
        self.lock = Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.mesh = meshLoop(self.sock, self.onMeshMessage)
        self.antFactory = AntFactory(self.onAntMessage)
        self.antFactory.enableFilter()
        self.antFactory.addToFilter(config["bikeId"])
        self.node = Node(PcapDriver("19052.pcap"), 'DemoNode')
        self.node.enableRxScanMode()

    @synchronized
    def sendJsonMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sendMessage(payload)

    @synchronized
    def sendJsonMeshMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sock.sendto(payload, 0, ("255.255.255.255", config["meshPort"]))

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")
        self.sock.bind(('', config["meshPort"]))
        self.node.start(self.antFactory.parseMessage, self.onAntErrorMessage)
        self.mesh.start()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                obj = json.loads(payload.decode('utf8'))
                for key, value in obj.items():
                    try:
                        getattr(self, 'onCommand' + key)(value)
                    except Exception as e:
                        print(e)
            except Exception as e:
                print(e)

    def onMeshMessage(self, payload):
        try:
            obj = json.loads(payload.decode('utf8'))
            for key, value in obj.items():
                try:
                    getattr(self, 'onMeshCommand' + key)(value)
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)

    def onAntMessage(self, payload):
        if payload.msg.deviceType == 121:  # S&C
            self.sendJsonMeshMessage({"Update": {
                payload.msg.deviceNumber: {
                    "cadence": payload.cadence,
                    "speed": payload.speed(2096),
                }
            }})
        elif payload.msg.deviceType == 11:  # Power
            self.sendJsonMeshMessage({"Update": {
                payload.msg.deviceNumber: {
                    "power": payload.averagePower,
                }
            }})

    def onAntErrorMessage(self, e):
        print(e)

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))
        self.node.stop()
        if self.mesh.is_alive():
            self.mesh.stop()
            self.mesh.join()
            self.sock.close()

    def onCommandSetDifficulty(self, data=None):
        if data == "easy":
            # Set stepper motor position
            pass
        if data == "hard":
            # Set stepper motor position
            pass

    def onCommandStartRace(self, data=None):
        self.sendJsonMeshMessage({"StartRace": config["bikeId"]})

    def onCommandStopRace(self, data=None):
        self.sendJsonMeshMessage({"StopRace": config["bikeId"]})

    def onMeshCommandStartRace(self, data=None):
        if data != config["bikeId"]:
            self.sendJsonMessage({"StartRace": data})

    def onMeshCommandStopRace(self, data=None):
        self.sendJsonMessage({"StopRace": data})

    def onMeshCommandUpdate(self, data=None):
        self.sendJsonMessage({"Update": data})

log.startLogging(sys.stdout)

factory = WebSocketServerFactory(u"ws://127.0.0.1:" + str(config["webSocketPort"]))
factory.protocol = MyServerProtocol

reactor.listenTCP(config["webSocketPort"], factory)
reactor.run()
