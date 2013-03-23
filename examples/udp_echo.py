"""UDP echo example.

Start server:

  >> python ./udp_echo.py --server

"""

import sys
import tulip

ADDRESS = ('127.0.0.1', 10000)


class MyServerUdpEchoProtocol:

    def connection_made(self, transport):
        print('start', transport)
        self.transport = transport

    def datagram_received(self, data, addr):
        print('Data received:', data, addr)
        self.transport.sendto(data, addr)

    def connection_refused(self, exc):
        print('Connection refused:', exc)

    def connection_lost(self, exc):
        print('stop', exc)


class MyClientUdpEchoProtocol:

    message = 'This is the message. It will be repeated.'

    def connection_made(self, transport):
        self.transport = transport
        print('sending "%s"' % self.message)
        self.transport.sendto(self.message.encode())
        print('waiting to receive')

    def datagram_received(self, data, addr):
        print('received "%s"' % data.decode())
        self.transport.close()

    def connection_refused(self, exc):
        print('Connection refused:', exc)

    def connection_lost(self, exc):
        print('closing transport', exc)
        loop = tulip.get_event_loop()
        loop.stop()


def start_server():
    loop = tulip.get_event_loop()
    tulip.Task(loop.create_datagram_endpoint(
        MyServerUdpEchoProtocol, local_addr=ADDRESS))
    loop.run_forever()


def start_client():
    loop = tulip.get_event_loop()
    tulip.Task(loop.create_datagram_endpoint(
        MyClientUdpEchoProtocol, remote_addr=ADDRESS))
    loop.run_forever()


if __name__ == '__main__':
    if '--server' in sys.argv:
        start_server()
    else:
        start_client()
