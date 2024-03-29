import asyncio
import json
import socket
from threading import Lock, Thread, Event

import zmq
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
from libAnt.drivers.pcap import PcapDriver
from libAnt.drivers.serial import SerialDriver
from libAnt.node import Node
from libAnt.profiles.factory import Factory as AntFactory

config = {  # default values
    "bikeId": 0,
    "webSocketPort": 8080,
    "webSocketIP": "127.0.0.1",
    "meshPort": 9999,
    "meshBufferSize": 5000,
    "debugAntPcap": False,
    "antSerialDev": "/dev/ttyUSB0",
    "disableAntFilter": False,
}

# Parse config values
try:
    with open("/boot/settings.txt", 'r') as file:
        for line in file:
            try:
                key, value = line.strip('"\n').split('=')
                if key[0] != "#":
                    config[key] = value
            except ValueError:
                pass
except FileNotFoundError as e:
    try:
        with open("settings.txt", 'r') as file:
            for line in file:
                try:
                    key, value = line.strip('"\n').split('=')
                    if key[0] != "#":
                        config[key] = value
                except ValueError:
                    pass
    except FileNotFoundError as e:
        print(e)

motor = False

try:
    from motor import motor
    motor = motor()
except:
    print("Stepper motor support disabled!")

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
                msg, addrinfo = self.sock.recvfrom(int(config["meshBufferSize"]))
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
        if not bool(config["disableAntFilter"]):
            self.antFactory.enableFilter()
            self.antFactory.addToFilter(int(config["bikeId"]))
        if bool(config["debugAntPcap"]):
            self.node = Node(PcapDriver(config["debugAntPcap"]))
        else:
            self.node = Node(SerialDriver(config["antSerialDev"]))
        self.node.enableRxScanMode()

    def sendJsonMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sendMessage(payload=payload)

    def sendJsonMeshMessage(self, msg):
        payload = json.dumps(msg, ensure_ascii=False).encode('utf8')
        self.sock.sendto(payload, 0, ("255.255.255.255", int(config["meshPort"])))

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")
        self.sendJsonMessage({"CurrentPlayer": int(config["bikeId"])})
        self.sock.bind(('', int(config["meshPort"])))
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
            if payload.dataPageNumber == 16:  # Simple Power data page
                self.sendJsonMeshMessage({"Update": {
                    payload.msg.deviceNumber: {
                        "power": payload.averagePower,
                    }
                }})

    def onAntErrorMessage(self, e):
        print(e)

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))
        if motor:
            motor.high()
        self.sock.close()
        self.node.stop()
        if self.mesh.is_alive():
            print("Waiting for mesh thread to stop...")
            self.mesh.stop()
            self.mesh.join()
            print("Mesh thread finished...")


    def onCommandSetDifficulty(self, data=None):
        if motor and data == "easy":
            self.factory.loop.call_soon_threadsafe(motor.low())
        if motor and data == "hard":
            self.factory.loop.call_soon_threadsafe(motor.high())

    def onCommandStartSequence(self, data=None):
        self.sendJsonMeshMessage({"StartSequence": int(config["bikeId"])})

    def onCommandStopRace(self, data=None):
        self.sendJsonMeshMessage({"StopRace": int(config["bikeId"])})

    def onCommandReadyForRace(self, data=None):
        self.sendJsonMeshMessage({"ReadyForRace": int(config["bikeId"])})

    def onMeshCommandStartSequence(self, data=None):
        self.sendJsonMessage({"StartSequence": int(config["bikeId"])})

    def onMeshCommandReadyForRace(self, data=None):
        self.sendJsonMessage({"ReadyForRace": int(config["bikeId"])})

    def onMeshCommandStopRace(self, data=None):
        self.sendJsonMessage({"StopRace": int(config["bikeId"])})

    def onMeshCommandUpdate(self, data=None):
        self.sendJsonMessage({"Update": data})


factory = WebSocketServerFactory(u"ws://" + str(config["webSocketIP"]) + ":" + str(config["webSocketPort"]))
factory.protocol = MyServerProtocol

loop = asyncio.get_event_loop()
coro = loop.create_server(factory, str(config["webSocketIP"]), int(config["webSocketPort"]))
server = loop.run_until_complete(coro)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    server.close()
    loop.close()
