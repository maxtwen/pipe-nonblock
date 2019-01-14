import fcntl
import io
import os
import socket

from pipe_nonblock.calls import BlockReceiver, NonBlockReceiver, BlockSender, NonBlockSender


class DuplexConnection:
    def __init__(self, receiver, sender):
        self._receiver = receiver
        self._sender = sender

    def send(self, *args, **kwargs):
        self._sender.send(*args, **kwargs)

    def send_bytes(self, *args, **kwargs):
        self._sender.send_bytes(*args, **kwargs)

    def recv(self, *args, **kwargs):
        return self._receiver.recv(*args, **kwargs)

    def recv_bytes(self, *args, **kwargs):
        return self._receiver.recv_bytes(*args, **kwargs)


def _get_receiver(nonblock):
    if nonblock:
        return NonBlockReceiver
    return BlockReceiver


def _get_sender(nonblock):
    if nonblock:
        return NonBlockSender
    return BlockSender


def _get_duplex_connection(nonblock, sock):
    return DuplexConnection(_get_receiver(nonblock)(sock), _get_sender(nonblock)(sock))


def Pipe(duplex=True, conn1_nonblock=True, conn2_nonblock=True):
    if duplex:
        s1, s2 = socket.socketpair()
        conn1 = _get_duplex_connection(conn1_nonblock, s1.detach())
        conn2 = _get_duplex_connection(conn2_nonblock, s2.detach())
        return conn1, conn2

    else:
        p1, p2 = os.pipe()
        receiver = _get_receiver(conn1_nonblock)(p1)
        sender = _get_sender(conn2_nonblock)(p2)
        return receiver, sender
