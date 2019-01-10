import fcntl
import io
import os
import pickle
import socket
import struct
from os import read


class _ConnectionBase:
    _handle = None

    def __init__(self, handle, readable=True, writable=True, r_block=False, w_block=False):
        handle = handle.__index__()
        if handle < 0:
            raise ValueError("invalid handle")
        if not readable and not writable:
            raise ValueError(
                "at least one of `readable` and `writable` must be True")
        self._handle = handle
        self._readable = readable
        self._writable = writable
        self._rbuf = io.BytesIO()
        self._remaining = None
        self._wbuf = b''
        self.r_block, self.w_block = r_block, w_block
        if self.r_block:
            self.recv = self._blocking_recv
        else:
            self.recv = self._non_blocking_recv

    def __del__(self):
        if self._handle is not None:
            self._close()

    def _check_closed(self):
        if self._handle is None:
            raise OSError("handle is closed")

    def _check_readable(self):
        if not self._readable:
            raise OSError("connection is write-only")

    def _check_writable(self):
        if not self._writable:
            raise OSError("connection is read-only")

    def _bad_message_length(self):
        if self._writable:
            self._readable = False
        else:
            self.close()
        raise OSError("bad message length")

    @property
    def closed(self):
        """True if the connection is closed"""
        return self._handle is None

    @property
    def readable(self):
        """True if the connection is readable"""
        return self._readable

    @property
    def writable(self):
        """True if the connection is writable"""
        return self._writable

    def fileno(self):
        """File descriptor or handle of the connection"""
        self._check_closed()
        return self._handle

    def close(self):
        """Close the connection"""
        if self._handle is not None:
            try:
                self._close()
            finally:
                self._handle = None

    def send_bytes(self, buf, offset=0, size=None):
        """Send the bytes data from a bytes-like object"""
        self._check_closed()
        self._check_writable()
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

    def send(self, obj):
        """Send a (picklable) object"""
        self._check_closed()
        self._check_writable()
        self._send_bytes(pickle.dumps(obj))

    def recv_bytes(self, maxlength=None):
        """
        Receive bytes data as a bytes object.
        """
        self._check_closed()
        self._check_readable()
        if maxlength is not None and maxlength < 0:
            raise ValueError("negative maxlength")
        buf = self._recv_bytes(maxlength)
        if buf is None:
            self._bad_message_length()
        return buf.getvalue()

    def recv_bytes_into(self, buf, offset=0):
        """
        Receive bytes data into a writeable bytes-like object.
        Return the number of bytes read.
        """
        self._check_closed()
        self._check_readable()
        with memoryview(buf) as m:
            # Get bytesize of arbitrary buffer
            itemsize = m.itemsize
            bytesize = itemsize * len(m)
            if offset < 0:
                raise ValueError("negative offset")
            elif offset > bytesize:
                raise ValueError("offset too large")
            result = self._recv_bytes()
            size = result.tell()
            if bytesize < offset + size:
                raise BufferTooShort(result.getvalue())
            # Message can fit in dest
            result.seek(0)
            result.readinto(m[offset // itemsize:
                              (offset + size) // itemsize])
            return size

    def _recv_checks(self):
        self._check_closed()
        self._check_readable()

    def _non_blocking_recv(self):
        self._recv_checks()
        objects = []
        while True:
            try:
                objects.append(self._recv_obj())
            except BlockingIOError:
                return objects

    def _blocking_recv(self):
        self._recv_checks()
        return self._recv_obj()

    def _recv_obj(self):
        self._recv_bytes()
        buf = self._rbuf.getbuffer()
        self._rbuf = io.BytesIO()
        return pickle.loads(buf)

    def poll(self, timeout=0.0):
        """Whether there is any input available to be read"""
        self._check_closed()
        self._check_readable()
        return self._poll(timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()


class _Connection(_ConnectionBase):
    """
    Connection class based on an arbitrary file descriptor (Unix only), or
    a socket handle (Windows).
    """

    def _close(self, _close=os.close):
        _close(self._handle)

    _write = os.write
    _read = os.read

    def _send(self, write=_write):
        remaining = len(self._wbuf)
        while True:
            try:
                n = write(self._handle, self._wbuf)
            except BlockingIOError:
                return
            self._wbuf = self._wbuf[n:]
            remaining -= n
            if remaining == 0:
                break

    def _recv(self, read=_read):
        handle = self._handle
        while self._remaining > 0:
            chunk = read(handle, self._remaining)
            n = len(chunk)
            if n == 0:
                raise OSError("got end of file during message")
            self._rbuf.write(chunk)
            self._remaining -= n

    def _send_bytes(self, buf):
        n = len(buf)
        if n > 0x7fffffff:
            pre_header = struct.pack("!i", -1)
            header = struct.pack("!Q", n)
            # self._send(pre_header)
            # self._send(header)
            # self._send(buf)
            self._wbuf += pre_header + header + buf
        else:
            # For wire compatibility with 3.7 and lower
            header = struct.pack("!i", n)
            if n > 16384:
                # The payload is large so Nagle's algorithm won't be triggered
                # and we'd better avoid the cost of concatenation.
                # self._send(header)
                # self._send(buf)
                self._wbuf += header + buf
            else:
                # Issue #20540: concatenate before sending, to avoid delays due
                # to Nagle's algorithm on a TCP socket.
                # Also note we want to avoid sending a 0-length buffer separately,
                # to avoid "broken pipe" errors if the other end closed the pipe.
                self._wbuf += header + buf
                # self._send(header + buf)
        self.flush()

    def flush(self):
        if not self._wbuf:
            return
        self._send()

    def _recv_bytes(self):
        if not self._remaining:
            buf = read(self._handle, 4)
            size, = struct.unpack("!i", buf)
            if size == -1:
                buf = read(self._handle, 8)
                size, = struct.unpack("!Q", buf)
            self._remaining = size
        self._recv()


def _set_non_blocking_flag(fd):
    oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)


def NonBlockingPipe(duplex=True, r_block=False, w_block=False):
    '''
    Returns pair of connection objects at either end of a pipe
    '''
    if duplex:
        s1, s2 = socket.socketpair()
        s1.setblocking(r_block)
        s2.setblocking(w_block)
        c1 = _Connection(s1.detach(), r_block=r_block, w_block=w_block)
        c2 = _Connection(s2.detach(), r_block=r_block, w_block=w_block)
    else:
        fd1, fd2 = os.pipe()
        if not r_block:
            _set_non_blocking_flag(fd1)
        if not w_block:
            _set_non_blocking_flag(fd2)
        c1 = _Connection(fd1, writable=False, r_block=r_block, w_block=w_block)
        c2 = _Connection(fd2, readable=False, r_block=r_block, w_block=w_block)

    return c1, c2
