# pipe-nonblock [![Build Status](https://travis-ci.org/maxtwen/Non-Blocking-Multiprocessing-Pipe.svg?branch=master)](https://travis-ci.org/maxtwen/Non-Blocking-Multiprocessing-Pipe)
Non-blocking multiprocessing pipe

## Installing

```bash
pip install pipe_nonblock
```

## Supported versions

- Python 3.4+

## Usage
```python3
from pipe_nonblock import Pipe

c1, c2 = Pipe(duplex=True, conn1_nonblock=True, conn2_nonblock=True) # create a new duplex non-blocking pipe
assert len(list(c2.recv(32))) == 0                                   # try receive data from a connection, it's empty at the moment 
c1.send('foo')                                                       # send python string object
buf, = c2.recv(32)                                                   # recv return generator with received objects
assert buf == 'foo'
c2.send('bar')
buf, = c1.recv(32)
assert buf == 'bar'
```

## Overview of Pipe function

```python
def Pipe(duplex, conn1_nonblock, conn1_nonblock) -> Tuple[connection1, connection2]:
```

| parameter  |type   | description  |
|---|---|---|
| duplex  | bool  | If duplex is True (the default) then the pipe is bidirectional. If duplex is False then the pipe is unidirectional: conn1 can only be used for receiving messages and conn2 can only be used for sending messages.  |
| conn1_nonblock  | bool  | If conn1_nonblock is True then the connection1 is  non-blocking  |
| conn2_nonblock  |bool   |  If conn2_nonblock is True then the connection2 is  non-blocking |