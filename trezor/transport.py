import struct
import mapping

class NotImplementedException(Exception):
    pass

class ConnectionError(Exception):
    pass

class Transport(object):
    def __init__(self, device, *args, **kwargs):
        self.device = device
        self.session_id = 0
        self.session_depth = 0
        self._open()

    def session_begin(self):
        """
        Apply a lock to the device in order to preform synchronous multistep "conversations" with the device.  For example, before entering the transaction signing workflow, one begins a session.  After the transaction is complete, the session may be ended.
        """
        if self.session_depth == 0:
            self._session_begin()
        self.session_depth += 1

    def session_end(self):
        """
        End a session.  Se session_begin for an in depth description of TREZOR sessions.
        """
        self.session_depth -= 1
        self.session_depth = max(0, self.session_depth)
        if self.session_depth == 0:
            self._session_end()

    def close(self):
        """
        Close the connection to the physical device or file descriptor represented by the Transport.
        """
        self._close()

    def write(self, msg):
        """
        Write mesage to tansport.  msg should be a member of a valid `protobuf class <https://developers.google.com/protocol-buffers/docs/pythontutorial>`_ with a SerializeToString() method.
        """
        raise NotImplementedException("Not implemented")

    def read(self):
        """
        If there is data available to be read from the transport, reads the data and tries to parse it as a protobuf message.  If the parsing succeeds, return a protobuf object.
        Otherwise, returns None.
        """
        if not self._ready_to_read():
            return None

        data = self._read()
        if data is None:
            return None

        return self._parse_message(data)

    def read_blocking(self):
        """
        Same as read, except blocks until data is available to be read.
        """
        while True:
            data = self._read()
            if data != None:
                break

        return self._parse_message(data)

    def _parse_message(self, data):
        (session_id, msg_type, data) = data

        # Raise exception if we get the response with
        # unexpected session ID
        self._check_session_id(session_id)

        if msg_type == 'protobuf':
            return data
        else:
            inst = mapping.get_class(msg_type)()
            inst.ParseFromString(bytes(data))
            return inst

    def _check_session_id(self, session_id):
        if self.session_id == 0:
            # Let the device set the session ID
            self.session_id = session_id
        elif session_id != self.session_id:
            # Session ID has been already set, but it differs from response
            raise Exception("Session ID mismatch. Have %d, got %d" % (self.session_id, session_id))

    # Functions to be implemented in specific transports:
    def _open(self):
        raise NotImplementedException("Not implemented")

    def _close(self):
        raise NotImplementedException("Not implemented")

    def _write_chunk(self, chunk):
        raise NotImplementedException("Not implemented")

    def _read_chunk(self):
        raise NotImplementedException("Not implemented")

    def _ready_to_read(self):
        """
        Returns True if there is data to be read from the transport.  Otherwise, False.
        """
        raise NotImplementedException("Not implemented")

    def _session_begin(self):
        pass

    def _session_end(self):
        pass

class TransportV1(Transport):
    def write(self, msg):
        ser = msg.SerializeToString()
        header = struct.pack(">HL", mapping.get_type(msg), len(ser))
        data = bytearray(b"##" + header + ser)

        while len(data):
            # Report ID, data padded to 63 bytes
            chunk = b'?' + data[:63] + b'\0' * (63 - len(data[:63]))
            self._write_chunk(chunk)
            data = data[63:]

    def _read(self):
        chunk = self._read_chunk()
        (msg_type, datalen, data) = self.parse_first(chunk)

        while len(data) < datalen:
            chunk = self._read_chunk()
            data.extend(self.parse_next(chunk))

        # Strip padding zeros
        data = data[:datalen]
        return (0, msg_type, data)

    def parse_first(self, chunk):
        if chunk[:3] != b"?##":
            raise Exception("Unexpected magic characters")

        try:
            headerlen = struct.calcsize(">HL")
            (msg_type, datalen) = struct.unpack(">HL", chunk[3:3 + headerlen])
        except:
            raise Exception("Cannot parse header length")

        data = chunk[3 + headerlen:]
        return (msg_type, datalen, data)

    def parse_next(self, chunk):
        if chunk[0:1] != b"?":
            raise Exception("Unexpected magic characters")

        return chunk[1:]

class TransportV2(Transport):
    def write(self, msg):
        ser = msg.SerializeToString()
        raise NotImplemented()

    def _read(self):
        pass

    def read_headers(self, read_f):
        c = read_f.read(2)
        if c != b"?!":
            raise Exception("Unexpected magic characters")

        try:
            headerlen = struct.calcsize(">HL")
            (session_id, msg_type, datalen) = struct.unpack(">LLL", read_f.read(headerlen))
        except:
            raise Exception("Cannot parse header length")

        return (0, msg_type, datalen)
