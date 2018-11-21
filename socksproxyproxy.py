#!/usr/bin/env python3

import socket
import socks
import threading
import socketserver
import select
import sys

class NormalClient:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))


class SocksClient:
    def __init__(self, host, port):
        self.sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.set_proxy(socks.SOCKS5, "localhost", 7654)
        self.sock.connect((host.decode('utf-8'), port))


class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):

    def handle(self):
        remote_host = None
        remote_port = None
        headers = b''
        while True:
            line = self.rfile.readline()
            if remote_host is None:
                req_split = line.split(b'/')
                try:
                    host_split = req_split[2].split(b':')
                except IndexError:
                    return
                remote_host = host_split[0]
                remote_port = int(host_split[1]) if len(host_split) > 1 else 80
                line = req_split[0].split()[0] + b' /' + b'/'.join(req_split[3:])
            line = line.replace(b'Connection: keep-alive', b'Connection: close')
            headers += line
                                
            if not line.strip():
                break
        client = NormalClient(remote_host, remote_port)
        client.sock.send(headers)
        response = client.sock.recv(4096)
        target_data = b''
        client_data = b''
        if (b'307 Temporary Redirect' and b'193.182.166') or (b'302 Moved Temporarily' and b'secdns.dk') in response:
            client.sock.close()
            client = SocksClient(remote_host, remote_port)
            client.sock.send(headers)
        else:
            client_data = response
        self.request.setblocking(0)
        client.sock.setblocking(0)
        terminate = False
        while not terminate:
            inputs = [self.request, client.sock]
            output = []
            if len(client_data) > 0:
                output.append(self.request)
            if len(target_data) > 0:
                output.append(client.sock)
                
            inputs_ready, outputs_ready, errors_ready = select.select(inputs, output, [], 1.0)
            for inp in inputs_ready:
                if inp == self.request:
                    data = self.request.recv(4096)
                    if data is not None:
                        if len(data) > 0:
                            target_data += data
                        else:
                            terminate = True
                elif inp == client.sock:
                    data = client.sock.recv(4096)
                    if data is not None:
                        if len(data) > 0:
                            client_data += data
                        else:
                            terminate = True
            for outp in outputs_ready:
                if outp == self.request and len(client_data) > 0:
                    bytes_written = self.request.send(client_data)
                    if bytes_written > 0:
                        client_data = client_data[bytes_written:]
                elif outp == client.sock and len(target_data) > 0:
                    bytes_written = client.sock.send(target_data)
                    if bytes_written > 0:
                        target_data = target_data[bytes_written:]
                        
        client.sock.close()
            
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    HOST, PORT = "localhost", 8081

    socketserver.TCPServer.allow_reuse_address = True
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    print(server.server_address)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    server_thread.join()

    server.shutdown()
    server.server_close()
