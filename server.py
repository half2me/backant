import json
import sys

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from libAnt.drivers.pcap import PcapDriver
from libAnt.node import Node
from libAnt.profiles.factory import Factory as AntFactory
from twisted.internet import reactor
from twisted.python import log


class MyServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super().__init__()
        self.antFactory = AntFactory(self.onAntMessage)
        #self.antFactory.enableFilter()
        #self.antFactory.addToFilter(11111)
        self.node = Node(PcapDriver("dummy.cap"), 'PcapNode')
        self.node.enableRxScanMode()
        self.node.start(self.antFactory.parseMessage, self.onAntErrorMessage)

    def sendJsonMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sendMessage(payload)

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
