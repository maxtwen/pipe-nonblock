# coding: utf-8
import math
import os
import pickle

from pipe_nonblock.calls import NonBlockReceiver, BlockSender


class TestObject:
    pass


def test_main():
    r, w = os.pipe()
    send_call = BlockSender(w)
    receiver = NonBlockReceiver(r)
    send_call.send(TestObject())
    obj, = receiver.recv(64)
    assert isinstance(obj, TestObject)


def test_partial_recv():
    r, w = os.pipe()
    sender = BlockSender(w)
    receiver = NonBlockReceiver(r)

    obj = TestObject()
    sender.send(obj)

    packed = sender._pack(pickle.dumps(obj))
    size = packed.size + len(packed.header)

    part1 = int(math.ceil(size / 2.))
    part2 = int(math.floor(size / 2.))

    list(receiver.recv(part1))
    obj, = receiver.recv(part2)
    assert isinstance(obj, TestObject)


if __name__ == '__main__':
    test_main()
    test_partial_recv()
