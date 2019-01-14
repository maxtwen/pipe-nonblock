# coding: utf-8
from pipe_nonblock import Pipe


def test_duplex_pipe():
    c1, c2 = Pipe(conn1_nonblock=True, conn2_nonblock=True)
    assert len(list(c2.recv(32))) == 0
    c1.send('foo')
    buf, = c2.recv(32)
    assert buf == 'foo'
    c2.send('bar')
    buf, = c1.recv(32)
    assert buf == 'bar'


def test_simplex_pipe():
    c1, c2 = Pipe(duplex=False, conn1_nonblock=True, conn2_nonblock=True)
    c2.send('foobar')
    buf, = c1.recv(32)
    assert buf == 'foobar'


if __name__ == '__main__':
    test_duplex_pipe()
    test_simplex_pipe()
