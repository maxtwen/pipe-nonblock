# coding: utf-8
from pipe_nonblock import Pipe


def test_duplex_pipe():
    c1, c2 = Pipe(conn1_nonblock=False, conn2_nonblock=False)
    c1.send(b'foo')
    assert c2.recv(3) == b'foo'
    c2.send(b'bar')
    assert c1.recv(3) == b'bar'


def test_simplex_pipe():
    c1, c2 = Pipe(duplex=False, conn1_nonblock=False, conn2_nonblock=False)
    c2.send(b'foobar')
    assert c1.recv(6) == b'foobar'


if __name__ == '__main__':
    test_duplex_pipe()
    test_simplex_pipe()
