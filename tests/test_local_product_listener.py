"""Real loopback TCP restart/exclusivity; no database or Windows simulation."""
import errno,socket,sys
import pytest
from scripts.local_product import _loopback_listener
pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Linux local product only')


def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def test_live_endpoint_is_already_listening_and_cannot_be_taken_over():
    port=free_port()
    with _loopback_listener(port) as original:
        assert original.getsockname()==('127.0.0.1',port)
        assert original.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
        with pytest.raises(OSError) as caught:
            with _loopback_listener(port):pytest.fail('active endpoint shared')
        assert caught.value.errno==errno.EADDRINUSE
        assert original.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1


def test_server_first_close_time_wait_can_reopen_original_endpoint():
    port=free_port()
    with _loopback_listener(port) as original:
        with socket.create_connection(('127.0.0.1',port),timeout=2) as client:
            accepted,_=original.accept()
            with accepted:
                client.sendall(b'owned request');assert accepted.recv(100)==b'owned request'
                accepted.sendall(b'owned response');accepted.shutdown(socket.SHUT_WR)
                assert client.recv(100)==b'owned response'
                assert client.recv(1)==b''
            # Peer closes after the server's FIN, leaving server-side TIME_WAIT.
    with _loopback_listener(port) as reopened:
        assert reopened.getsockname()==('127.0.0.1',port)


def test_failing_startup_closes_original_socket_without_affecting_other_listener():
    port=free_port();other=free_port()
    with _loopback_listener(other) as retained:
        with pytest.raises(RuntimeError):
            with _loopback_listener(port):raise RuntimeError('owned startup failed')
        with _loopback_listener(port):
            assert retained.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
