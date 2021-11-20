"""Definition of a subclass derived from serial.threaded.Protocol used by
serial.threaded.ReaderThread.
"""

import logging
import queue
import threading

import serial

from serial import threaded

from smarthop import sr920

_logger = logging.getLogger(__name__)


class SR920Protocol(threaded.Protocol):
    """Represents a subclass derived from serial.threaded.Protocol used by
    serial.threaded.ReaderThread.
    """

    DMY = b"\xff"
    ESC = b"\x7d"
    SYN = b"\x7e"

    def __init__(self):
        _logger.debug("enter __init__()")

        self._buffer = bytearray()
        self._in_dummy = False
        self._in_command = False

        self._transport = None
        self._writer = None

        self._queue_out = queue.Queue(5)

        self._command_received_handler = None

    # overrides serial.threaded.Protocol.connection_made()
    def connection_made(self, transport):
        """Called when reader thread is started.

        Args:
            transport: An instance used to write to serial port.
        """
        _logger.debug("enter connection_made(): transport=%s", transport)

        self._transport = transport

        self._writer = threading.Thread(target=self._worker_writer, name="writer")
        self._writer.start()

    # overrides serial.threaded.Protocol.connection_lost()
    def connection_lost(self, exc):
        """Called when the serial port is closed or the reader loop terminated
        otherwise.

        Args:
            exc: Exception if connection was terminated by error, otherwise None.
        """
        _logger.debug("enter connection_lost(): exc=%s", exc)

        self._transport = None
        self._writer.join()

        super().connection_lost(exc)

    # overrides serial.threaded.Protocol.data_received()
    def data_received(self, data):
        """Called when data is received from the serial port.

        Args:
            data: Partial received data.
        """
        _logger.debug("enter data_received(): data=%s", data)

        for byte in serial.iterbytes(data):
            if self._in_dummy:
                if byte == SR920Protocol.SYN:
                    self._buffer.clear()
                    self._in_dummy = False
                elif byte != SR920Protocol.DMY:
                    _logger.warning(
                        "ignore invalid character in dummy header: %s", byte
                    )
            elif self._in_command:
                if byte == SR920Protocol.SYN:
                    unescaped = SR920Protocol._unescape(self._buffer)
                    cmd_received = sr920.SR920Command.parse(unescaped)

                    _logger.info("command received: %s", cmd_received)

                    if self._command_received_handler:
                        self._command_received_handler(cmd_received)

                    self._buffer.clear()
                    self._in_command = False
                else:
                    self._buffer.extend(byte)
            else:
                if byte in (SR920Protocol.DMY, SR920Protocol.SYN):
                    if len(self._buffer) > 0:
                        _logger.warning(
                            "ignore buffers received "
                            "before dummy header or command: %s",
                            self._buffer,
                        )

                        self._buffer.clear()

                    self._in_dummy = byte == SR920Protocol.DMY
                    self._in_command = byte == SR920Protocol.SYN
                else:
                    self._buffer.extend(byte)

    def send_command(self, cmd_to_send):
        """Sends the specified API command to the module.

        Args:
            cmd_to_send: An instance of the SR920Command class.
        """
        _logger.debug("enter send_command(): cmd_to_send=%s", cmd_to_send)

        try:
            self._queue_out.put_nowait(cmd_to_send)
        except queue.Full as exc:
            _logger.warning("outgoing queue is full: %s", exc)

    def set_command_received_handler(self, handler):
        """Sets a handler for the command_received event.

        Args:
            handler: A handler for the command_received event.
                A handler should be defined as follows:
                    def command_received_handler(bytes)
        """
        _logger.debug("enter set_command_received_handler(): handler=%s", handler)

        self._command_received_handler = handler

    @classmethod
    def _escape(cls, data):
        _logger.debug("enter _escape(): data=%s", data)

        value = bytearray()

        for byte in serial.iterbytes(data):
            if byte in (cls.ESC, cls.SYN):
                value.extend(cls.ESC)
                value.extend(bytes([byte[0] ^ 0x20]))
            else:
                value.extend(byte)

        _logger.debug("escaped data: %s", value)

        return value

    @classmethod
    def _unescape(cls, data):
        _logger.debug("enter _unescape(): data=%s", data)

        value = bytearray()

        in_escape = False

        for byte in serial.iterbytes(data):
            if in_escape:
                value.extend(bytes([byte[0] ^ 0x20]))
                in_escape = False
            else:
                if byte == cls.ESC:
                    in_escape = True
                else:
                    value.extend(byte)

        _logger.debug("unescaped data: %s", value)

        return value

    def _worker_writer(self):
        _logger.debug("enter _worker_writer()")

        while self._transport:
            if not self._queue_out.empty():
                try:
                    cmd_to_send = self._queue_out.get_nowait()

                    _logger.info("send command: %s", cmd_to_send)

                    header = SR920Protocol.DMY * 7 + SR920Protocol.SYN
                    data = (
                        header
                        + SR920Protocol.SYN
                        + SR920Protocol._escape(cmd_to_send.to_bytes())
                        + SR920Protocol.SYN
                    )

                    self._transport.write(data)

                    _logger.debug("data sent: %s", data)
                except queue.Empty as exc:
                    _logger.warning("outgoing queue is empty: %s", exc)

        _logger.debug("exit _worker_writer()")
