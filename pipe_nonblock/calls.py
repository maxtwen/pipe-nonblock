# coding: utf-8
import fcntl
import io
import os
import pickle
import struct
from collections import namedtuple
from io import BlockingIOError
from os import read


class Call:
    def __init__(self, handle):
        self._handle = handle

    def fileno(self):
        return self._handle.fileno()

    def _check_closed(self):
        if self._handle is None:
            raise OSError("handle is closed")

    def close(self):
        """Close the connection"""
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None

    @staticmethod
    def _set_non_block_flag(fd):
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)


class Receiver(Call):
    def recv(self, maxlength):
        raise NotImplementedError

    def recv_bytes(self, maxlength):
        raise NotImplementedError


ObjectBytes = namedtuple('ObjectBytes', ['pre_header', 'header', 'buf', 'size'])


class Sender(Call):

    def send(self, obj):
        """Send a (picklable) object"""
        self._check_closed()
        self._send_bytes(pickle.dumps(obj))

    def send_bytes(self, buf, offset=0, size=None):
        """Send the bytes data from a bytes-like object"""
        self._check_closed()
        m = memoryview(buf)
        # HACK for byte-indexing of non-bytewise buffers (e.g. array.array)
        if m.itemsize > 1:
            m = memoryview(bytes(m))
        n = len(m)
        if offset < 0:
            raise ValueError("offset is negative")
        if n < offset:
            raise ValueError("buffer length < offset")
        if size is None:
            size = n - offset
        elif size < 0:
            raise ValueError("size is negative")
        elif offset + size > n:
            raise ValueError("buffer length < offset + size")
        self._send_bytes(m[offset:offset + size])

    def _send_bytes(self, buf):
        raise NotImplementedError

    def _pack(self, buf):
        n = len(buf)
        if n > 0x7fffffff:
            pre_header = struct.pack("!i", -1)
            header = struct.pack("!Q", n)
            return ObjectBytes(pre_header, header, buf, n)
        else:
            # For wire compatibility with 3.7 and lower
            header = struct.pack("!i", n)
            return ObjectBytes(None, header, buf, n)


class ObjectContext:
    def __init__(self, buf, remaining_bytes):
        self.buf = buf
        self.remaining_bytes = remaining_bytes


class NonBlockReceiver(Receiver):
    def __init__(self, handle):
        self._set_non_block_flag(handle)
        Receiver.__init__(self, handle)
        self._obj_context = None
        self._object_bytes = b''

    def recv_bytes(self, maxlength):
        buf = b''
        try:
            buf = read(self._handle, maxlength)
        except BlockingIOError:
            pass
        return buf

    def recv(self, maxlength):
        self._check_closed()
        self._object_bytes = self.recv_bytes(maxlength)
        while self._object_bytes:
            if self._obj_context:
                buf = self._object_bytes[:self._obj_context.remaining_bytes]
                self._obj_context.remaining_bytes -= len(buf)
                self._obj_context.buf.write(buf)
                if self._obj_context.remaining_bytes == 0:
                    obj = pickle.loads(self._obj_context.buf.getvalue())
                    yield obj
                    self._obj_context = None
                else:
                    return
            else:
                if not self._object_bytes:
                    return
                if len(self._object_bytes) < 4:
                    return
                size, = struct.unpack("!i", self._object_bytes[:4])
                if size == -1:
                    if len(self._object_bytes) < 8:
                        return
                    size, = struct.unpack("!Q", self._object_bytes[:8])
                    self._object_bytes = self._object_bytes[8:]
                else:
                    self._object_bytes = self._object_bytes[4:]
                self._obj_context = ObjectContext(io.BytesIO(), size)


class BlockReceiver(Receiver):
    def recv(self, maxlength):
        """Receive a (picklable) object"""
        self._check_closed()
        buf = self._recv_bytes()
        return pickle.loads(buf.getbuffer())

    def recv_bytes(self, maxlength=None):
        """
        Receive bytes data as a bytes object.
        """
        self._check_closed()
        if maxlength is not None and maxlength < 0:
            raise ValueError("negative maxlength")
        buf = self._recv_bytes(maxlength)
        if buf is None:
            raise OSError("bad message length")
        return buf.getvalue()

    def _recv_bytes(self, maxsize=None):
        buf = self._recv(4)
        size, = struct.unpack("!i", buf.getvalue())
        if size == -1:
            buf = self._recv(8)
            size, = struct.unpack("!Q", buf.getvalue())
        if maxsize is not None and size > maxsize:
            return None
        return self._recv(size)

    def _recv(self, size):
        buf = io.BytesIO()
        handle = self._handle
        remaining = size
        while remaining > 0:
            chunk = read(handle, remaining)
            n = len(chunk)
            if n == 0:
                if remaining == size:
                    raise EOFError
                else:
                    raise OSError("got end of file during message")
            buf.write(chunk)
            remaining -= n
        return buf


class NonBlockSender(Sender):
    def __init__(self, handle):
        self._set_non_block_flag(handle)
        Sender.__init__(self, handle)
        self._buf = b''

    def _send_bytes(self, buf):
        packed = self._pack(buf)
        if packed.pre_header:
            self._buf += b''.join((packed.pre_header, packed.header, packed.buf))
        else:
            self._buf += packed.header + packed.buf
        self.drain()

    def _send(self):
        remaining = len(self._buf)
        while True:
            try:
                n = os.write(self._handle, self._buf)
            except BlockingIOError:
                return
            self._buf = self._buf[n:]
            remaining -= n
            if remaining == 0:
                break

    def drain(self):
        if not self._buf:
            return
        self._send()


class BlockSender(Sender):

    def _send(self, buf):
        remaining = len(buf)
        while True:
            n = os.write(self._handle, buf)
            remaining -= n
            if remaining == 0:
                break
            buf = buf[n:]

    def _send_bytes(self, buf):
        packed = self._pack(buf)
        if packed.pre_header:
            self._send(packed.pre_header)
            self._send(packed.header)
            self._send(packed.buf)
        else:
            if packed.size > 16384:
                # The payload is large so Nagle's algorithm won't be triggered
                # and we'd better avoid the cost of concatenation.
                self._send(packed.header)
                self._send(packed.buf)
            else:
                # Issue #20540: concatenate before sending, to avoid delays due
                # to Nagle's algorithm on a TCP socket.
                # Also note we want to avoid sending a 0-length buffer separately,
                # to avoid "broken pipe" errors if the other end closed the pipe.
                self._send(packed.header + packed.buf)
