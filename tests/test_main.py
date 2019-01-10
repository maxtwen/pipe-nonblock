from non_blocking_pipe.pipe import NonBlockingPipe


class Object:
    pass


def write_to_pipe(w_pipe):
    w_pipe.send(Object())


def test_main():
    r_pipe, w_pipe = NonBlockingPipe()
    w_pipe.send(Object())
    w_pipe.send(Object())
    objects = r_pipe.recv()
    assert len(objects) == 2
    for object in objects:
        assert isinstance(object, Object)
    objects = r_pipe.recv()
    assert not objects


def test_blocking_recv():
    r_pipe, w_pipe = NonBlockingPipe(r_block=True)
    w_pipe.send(Object())
    w_pipe.send(Object())
    object = r_pipe.recv()
    assert isinstance(object, Object)
    objects = r_pipe.recv()
    assert not objects


if __name__ == '__main__':
    test_main()
