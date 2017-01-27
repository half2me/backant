import json
import socket
import time
import zmq
import sys
from threading import Lock, Thread

import zmq
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from libAnt.drivers.pcap import PcapDriver
from libAnt.node import Node
from libAnt.profiles.factory import Factory as AntFactory
from twisted.internet import reactor
from twisted.python import log


class meshLoop(Thread):
    def __init__(self, socket, callback):
        super().__init__()
        self.sock = socket
        self.callback = callback

    def run(self):
        while True:
            msg, addrinfo = self.sock.recvfrom(5000)  # pick a suitable size :S
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
        self.sock.bind(('', 9999))
        self.mesh = meshLoop(self.sock, self.onMeshMessage)
        self.mesh.start()
        self.poller = zmq.Poller()
        self.poller.register(self.sock, zmq.POLLIN)
        self.antFactory = AntFactory(self.onAntMessage)
        #self.antFactory.enableFilter()
        #self.antFactory.addToFilter(11111)
        self.node = Node(PcapDriver("dummy.cap"), 'PcapNode')
        self.node.enableRxScanMode()
        self.node.start(self.antFactory.parseMessage, self.onAntErrorMessage)

    def sendJsonMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sendMessage(payload)

    def sendJsonMeshMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sock.sendto(payload, 0, ("255.255.255.255", 9999))

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")

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
        pass

    def onAntErrorMessage(self, error):
        pass

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

    def onCommandStartRace(self, data=None):
        pass

    def onCommandStopRace(self, data=None):
        pass

    def onMeshCommandStartRace(self, data=None):
        pass

    def onMeshCommandStopRace(self, data=None):
        pass

    def onMeshCommandUpdate(self, data=None):
        pass

log.startLogging(sys.stdout)

factory = WebSocketServerFactory(u"ws://127.0.0.1:9000")
factory.protocol = MyServerProtocol

reactor.listenTCP(9000, factory)
reactor.run()
