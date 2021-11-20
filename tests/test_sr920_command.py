"""Test cases for the smarthop.sr920.SR920Command class."""

import unittest

from smarthop import sr920


class TestSR920Command(unittest.TestCase):
    """Represents test cases for the smarthop.sr920.SR920Command class."""

    def setUp(self):
        # pylint: disable=line-too-long
        self.commands = [
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_REQUEST,
                    {
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                    },
                ),
                "bytes": b"\x07\x80\x02",
            },
            {  # enums
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                        "value": sr920.SR920TxPower.TX_20mW,
                    },
                ),
                "bytes": b"\x07\x81\x00\x02\x02",
            },
            {  # hex
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.MAC_ADDRESS,
                        "value": "0000000000000123",
                    },
                ),
                "bytes": b"\x07\x81\x00\x12\x23\x01\x00\x00\x00\x00\x00\x00",
            },
            {  # bool
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.LED,
                        "value": True,
                    },
                ),
                "bytes": b"\x07\x81\x00\x30\x01",
            },
            {  # int
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.DUMMY_SIZE,
                        "value": 8,
                    },
                ),
                "bytes": b"\x07\x81\x00\x31\x08",
            },
            {  # bool customized
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.ENABLE_ENCRYPTION,
                        "value": True,
                    },
                ),
                "bytes": b"\x07\x81\x00\xa6\x6a",
            },
            {  # object
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.NETWORK_ADDRESS,
                        "value": {
                            "short_address": "0001",
                            "pan_id": "0123",
                        },
                    },
                ),
                "bytes": b"\x07\x81\x00\xb2\x01\x00\x23\x01",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.WRITE_CONFIG_REQUEST,
                    {
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                        "value": sr920.SR920TxPower.TX_20mW,
                    },
                ),
                "bytes": b"\x07\x82\x02\x02\x02",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.WRITE_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                    },
                ),
                "bytes": b"\x07\x83\x00\x02",
            },
            {
                "command": sr920.SR920Command(sr920.SR920CommandId.SAVE_CONFIG_REQUEST),
                "bytes": b"\x07\x84",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SAVE_CONFIG_RESPONSE,
                    {
                        "result": 0,
                    },
                ),
                "bytes": b"\x07\x85\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.RESET_CONFIG_REQUEST
                ),
                "bytes": b"\x07\x86",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.RESET_CONFIG_RESPONSE,
                    {
                        "result": 0,
                    },
                ),
                "bytes": b"\x07\x87\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SEND_DATA_REQUEST,
                    {
                        "destination": "0001",
                        "source": "0010",
                        "nor": 3,
                        "security": True,
                        "ttl": 30,
                        "data": b"Hello",
                    },
                ),
                "bytes": b"\x07\xa0\x01\x00\x00\x10\x00\x00\x03\x0c\x1e\x48\x65\x6c\x6c\x6f",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SEND_DATA_RESPONSE,
                    {
                        "result": 0,
                        "destination": "0001",
                        "source": "0010",
                        "nor": 3,
                        "security": True,
                        "data": b"Hello",
                    },
                ),
                "bytes": b"\x07\xa1\x00\x01\x00\x00\x10\x00\x00\x03\x0e\x48\x65\x6c\x6c\x6f",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.DATA_RECEIVED_NOTIFICATION,
                    {
                        "destination": "0010",
                        "source": "0001",
                        "nor": 3,
                        "security": True,
                        "ttl": 30,
                        "data": b"Hello",
                    },
                ),
                "bytes": b"\x07\xa2\x10\x00\x00\x01\x00\x00\x03\x0e\x1e\x48\x65\x6c\x6c\x6f",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_RAM_CONFIG_REQUEST,
                    {
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                    },
                ),
                "bytes": b"\x07\xa5\x02",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.READ_RAM_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                        "value": sr920.SR920TxPower.TX_20mW,
                    },
                ),
                "bytes": b"\x07\xa6\x00\x02\x02",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.WRITE_RAM_CONFIG_REQUEST,
                    {
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                        "value": sr920.SR920TxPower.TX_20mW,
                    },
                ),
                "bytes": b"\x07\xa3\x02\x02",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.WRITE_RAM_CONFIG_RESPONSE,
                    {
                        "result": 0,
                        "config_id": sr920.SR920ConfigId.TX_POWER,
                    },
                ),
                "bytes": b"\x07\xa4\x00\x02",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.START_NETWORK_REQUEST,
                    {
                        "mode": sr920.SR920NetworkMode.START_NETWORK,
                    },
                ),
                "bytes": b"\x07\xa7\x04",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.START_NETWORK_RESPONSE,
                    {
                        "result": 0,
                        "mode": sr920.SR920NetworkMode.START_NETWORK,
                    },
                ),
                "bytes": b"\x07\xa8\x00\x04",
            },
            {  # ADDRESS_CHANGED
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
                    {
                        "state": sr920.SR920NetworkState.ADDRESS_CHANGED,
                        "short_address": "0001",
                        "pan_id": "0123",
                        "coordinator": "ffff",
                    },
                ),
                "bytes": b"\x07\xa9\x00\x01\x00\x23\x01\xff\xff",
            },
            {  # MODULE_INITIALIZED
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
                    {
                        "state": sr920.SR920NetworkState.MODULE_INITIALIZED,
                    },
                ),
                "bytes": b"\x07\xa9\x02",
            },
            {  # NODE_CONNECTED
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
                    {
                        "state": sr920.SR920NetworkState.NODE_CONNECTED,
                        "short_address": "0010",
                        "mac_address": "0000000000004567",
                    },
                ),
                "bytes": b"\x07\xa9\x03\x10\x00\x67\x45\x00\x00\x00\x00\x00\x00",
            },
            {  # NODE_DISCONNECTED
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
                    {
                        "state": sr920.SR920NetworkState.NODE_DISCONNECTED,
                        "short_address": "0010",
                        "mac_address": "0000000000004567",
                    },
                ),
                "bytes": b"\x07\xa9\x04\x10\x00\x67\x45\x00\x00\x00\x00\x00\x00",
            },
            {
                "command": sr920.SR920Command(sr920.SR920CommandId.RESET_REQUEST),
                "bytes": b"\x07\xf0\x01\x00",
            },
            {  # succeeded
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.RESET_RESPONSE,
                    {
                        "result": 0,
                    },
                ),
                "bytes": b"\x07\xf1\x00",
            },
            {  # failed
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.RESET_RESPONSE,
                    {
                        "result": 1,
                        "reset_parameter": b"\xff\xff\xff",
                    },
                ),
                "bytes": b"\x07\xf1\x01\xff\xff\xff",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SET_TIME_REQUEST,
                    {
                        "time_sec": 1609459200,
                        "time_usec": 0,
                    },
                ),
                "bytes": b"\x07\xf2\x00\x66\xee\x5f\x00\x00\x00\x00\x00\x00\x00\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SET_TIME_RESPONSE,
                    {
                        "result": 0,
                    },
                ),
                "bytes": b"\x07\xf3\x00",
            },
            {
                "command": sr920.SR920Command(sr920.SR920CommandId.GET_TIME_REQUEST),
                "bytes": b"\x07\xf4",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_TIME_RESPONSE,
                    {
                        "result": 0,
                        "time_sec": 1609459200,
                        "time_usec": 0,
                    },
                ),
                "bytes": b"\x07\xf5\x00\x00\x66\xee\x5f\x00\x00\x00\x00\x00\x00\x00\x00",
            },
            {
                "command": sr920.SR920Command(sr920.SR920CommandId.GET_VERSION_REQUEST),
                "bytes": b"\x07\xfa",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_VERSION_RESPONSE,
                    {
                        "result": 0,
                        "version": "SRMP02020005",
                    },
                ),
                "bytes": b"\x07\xfb\x00\x53\x52\x4d\x50\x30\x32\x30\x32\x30\x30\x30\x35",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NODE_LIST_REQUEST,
                    {
                        "list_type": sr920.SR920NodeListType.FIXED_ADDRESS,
                        "seq_no": 1,
                    },
                ),
                "bytes": b"\x03\x30\x00\x01\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NODE_LIST_RESPONSE,
                    {
                        "result": 0,
                        "seq_no": 1,
                        "node_list": [
                            {
                                "short_address": "0010",
                                "mac_address": "0000000000004567",
                            },
                            {
                                "short_address": "0011",
                                "mac_address": "00000000000089ab",
                            },
                        ],
                    },
                ),
                "bytes": b"\x03\x31\x00\x01\x00\x10\x00\x67\x45\x00\x00\x00\x00\x00\x00\x11\x00\xab\x89\x00\x00\x00\x00\x00\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_LINK_LIST_REQUEST,
                    {
                        "seq_no": 1,
                    },
                ),
                "bytes": b"\x03\x32\x01\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_LINK_LIST_RESPONSE,
                    {
                        "result": 0,
                        "seq_no": 1,
                        "link_list": [
                            {
                                "child": "0010",
                                "parent": "0001",
                            },
                            {
                                "child": "0011",
                                "parent": "0010",
                            },
                        ],
                    },
                ),
                "bytes": b"\x03\x33\x00\x01\x00\x10\x00\x01\x00\x11\x00\x10\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_ROUTE_REQUEST,
                    {
                        "target": "0011",
                    },
                ),
                "bytes": b"\x03\x34\x11\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_ROUTE_RESPONSE,
                    {
                        "result": 0,
                        "route_info": ["0011", "0010", "0001"],
                    },
                ),
                "bytes": b"\x03\x35\x00\x11\x00\x10\x00\x01\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RTT_REQUEST,
                    {
                        "target": "0011",
                        "length": 30,
                    },
                ),
                "bytes": b"\x03\x36\x11\x00\x1e",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RTT_RESPONSE,
                    {
                        "result": 0,
                        "rtt": 200,
                        "hop": 2,
                        "voltage": 300,
                    },
                ),
                "bytes": b"\x03\x37\x00\xc8\x00\x02\x2c\x01",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NEIGHBOR_INFO_REQUEST,
                    {
                        "target": "0011",
                    },
                ),
                "bytes": b"\x03\x38\x11\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NEIGHBOR_INFO_RESPONSE,
                    {
                        "result": 0,
                        "neighbor_list": [
                            {
                                "short_address": "0001",
                                "rssi": -40,
                                "link_cost": 1,
                                "hello": b"\xff",
                            },
                            {
                                "short_address": "0010",
                                "rssi": -50,
                                "link_cost": 1,
                                "hello": b"\xff",
                            },
                        ],
                    },
                ),
                "bytes": b"\x03\x39\x00\x01\x00\xd8\x01\xff\x10\x00\xce\x01\xff",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.CONTROL_FIXED_ADDRESS_REQUEST,
                    {
                        "mode": sr920.SR920FixedAddressControlMode.ADD,
                        "short_address": "0010",
                        "mac_address": "0000000000004567",
                    },
                ),
                "bytes": b"\x03\x40\x01\x10\x00\x67\x45\x00\x00\x00\x00\x00\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.CONTROL_FIXED_ADDRESS_RESPONSE,
                    {
                        "result": 0,
                        "short_address": "0010",
                        "mac_address": "0000000000004567",
                    },
                ),
                "bytes": b"\x03\x41\x00\x10\x00\x67\x45\x00\x00\x00\x00\x00\x00",
            },
            {  # START_SEND
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RADIO_STATUS_REQUEST,
                    {
                        "mode": sr920.SR920RadioMeasurementMode.START_SEND,
                        "target": "0001",
                        "count": 100,
                        "interval": 4000,
                        "length": 32,
                    },
                ),
                "bytes": b"\x03\x42\x01\x01\x00\x64\x00\xa0\x0f\x20\x00",
            },
            {  # START_RECEIVE
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RADIO_STATUS_REQUEST,
                    {
                        "mode": sr920.SR920RadioMeasurementMode.START_RECEIVE,
                        "target": "0010",
                    },
                ),
                "bytes": b"\x03\x42\x02\x10\x00",
            },
            {  # RESULT
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RADIO_STATUS_RESPONSE,
                    {
                        "result": 0,
                        "mode": sr920.SR920RadioMeasurementMode.RESULT,
                        "target": "0010",
                        "count": 100,
                        "rssi_max": -53,
                        "rssi_min": -56,
                        "rssi_ave_int": -53,
                        "rssi_ave_frac": 87,
                    },
                ),
                "bytes": b"\x03\x43\x00\x03\x10\x00\x64\x00\xcb\xc8\xcb\x57",
            },
            {  # ABORT
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.MEASURE_RADIO_STATUS_RESPONSE,
                    {
                        "result": 0,
                        "mode": sr920.SR920RadioMeasurementMode.ABORT,
                        "target": "0001",
                    },
                ),
                "bytes": b"\x03\x43\x00\x04\x01\x00",
            },
            {  # START
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST,
                    {
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.START,
                        "seq_no": 1,
                        "version": "SRMP02020005",
                        "size": 151754,
                        "checksum": b"\xd6\xcc",
                    },
                ),
                "bytes": b"\x07\x40\x01\x02\x00\x01\x00\x15\x00\x00\x05\x53\x52\x4d\x50\x30\x32\x30\x32\x30\x30\x30\x35\x00\x02\x50\xca\xd6\xcc",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_RESPONSE,
                    {
                        "result": 0,
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.START,
                        "seq_no": 1,
                        "length": 3,
                        "status": 0,
                    },
                ),
                "bytes": b"\x07\x41\x00\x02\x02\x00\x01\x00\x03\x00\x00\x00",
            },
            {  # WRITE
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST,
                    {
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.WRITE,
                        "seq_no": 1,
                        "page_no": 1,
                        "frame_no": 1,
                        "frame": b"\xff" * 1024,
                    },
                ),
                "bytes": b"\x07\x40\x01\x03\x00\x01\x04\x04\x00\x00\x01\x01"
                + b"\xff" * 1024,
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_RESPONSE,
                    {
                        "result": 0,
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.WRITE,
                        "seq_no": 1,
                        "length": 3,
                        "status": 0,
                    },
                ),
                "bytes": b"\x07\x41\x00\x02\x03\x00\x01\x00\x03\x00\x00\x00",
            },
            {  # CHECK
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST,
                    {
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.CHECK,
                        "seq_no": 1,
                        "last_page": 1,
                    },
                ),
                "bytes": b"\x07\x40\x01\x04\x00\x01\x00\x03\x00\x00\x01",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_RESPONSE,
                    {
                        "result": 0,
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.CHECK,
                        "seq_no": 1,
                        "length": 3,
                        "status": 0,
                    },
                ),
                "bytes": b"\x07\x41\x00\x02\x04\x00\x01\x00\x03\x00\x00\x00",
            },
            {  # RESET
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST,
                    {
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.RESET,
                        "seq_no": 1,
                        "wait": 1,
                    },
                ),
                "bytes": b"\x07\x40\x01\x05\x00\x01\x00\x02\x00\x01",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_RESPONSE,
                    {
                        "result": 0,
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.RESET,
                        "seq_no": 1,
                        "length": 1,
                        "status": 0,
                    },
                ),
                "bytes": b"\x07\x41\x00\x02\x05\x00\x01\x00\x01\x00",
            },
            {  # GET_VERSION
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST,
                    {
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.GET_VERSION,
                        "seq_no": 1,
                    },
                ),
                "bytes": b"\x07\x40\x01\x06\x00\x01\x00\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.UPDATE_FIRMWARE_RESPONSE,
                    {
                        "result": 0,
                        "sub_command_id": sr920.SR920FirmwareUpdateCommandId.GET_VERSION,
                        "seq_no": 1,
                        "length": 13,
                        "status": 0,
                        "version": "SRMP02020005",
                    },
                ),
                "bytes": b"\x07\x41\x00\x02\x06\x00\x01\x00\x0d\x00\x53\x52\x4d\x50\x30\x32\x30\x32\x30\x30\x30\x35",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_MY_NEIGHBOR_INFO_REQUEST
                ),
                "bytes": b"\x07\x44",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_MY_NEIGHBOR_INFO_RESPONSE,
                    {
                        "result": 0,
                        "neighbor_list": [
                            {
                                "short_address": "0001",
                                "rssi": -40,
                                "hop": 0,
                                "parent": "ffff",
                            },
                            {
                                "short_address": "0010",
                                "rssi": -50,
                                "hop": 1,
                                "parent": "0001",
                            },
                        ],
                    },
                ),
                "bytes": b"\x07\x45\x00\x01\x00\xd8\x00\xff\xff\x10\x00\xce\x01\x01\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NETWORK_ADDRESS_REQUEST
                ),
                "bytes": b"\x07\xf6",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.GET_NETWORK_ADDRESS_RESPONSE,
                    {
                        "result": 0,
                        "short_address": "0001",
                        "pan_id": "0123",
                        "coordinator": "ffff",
                    },
                ),
                "bytes": b"\x07\xf7\x00\x01\x00\x23\x01\xff\xff",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SCAN_CHANNEL_REQUEST,
                    {
                        "mode": sr920.SR920ChannelScanMode.START,
                        "channel": 33,
                        "count": 500,
                        "interval": 2,
                    },
                ),
                "bytes": b"\x07\x09\x00\x21\xf4\x01\x02\x00",
            },
            {
                "command": sr920.SR920Command(
                    sr920.SR920CommandId.SCAN_CHANNEL_RESPONSE,
                    {
                        "result": 0,
                        "mode": sr920.SR920ChannelScanMode.START,
                        "channel": 33,
                        "count": 500,
                        "interval": 2,
                        "rssi_max": -84,
                        "rssi_min": -92,
                        "rssi_ave": -8775,
                    },
                ),
                "bytes": b"\x07\x0a\x00\x00\x21\xf4\x01\x02\x00\xac\xa4\xb9\xdd",
            },
        ]

    def test_constructor(self):
        with_parameters = sr920.SR920Command(
            sr920.SR920CommandId.READ_CONFIG_REQUEST,
            {
                "config_id": sr920.SR920ConfigId.TX_POWER,
            },
        )

        self.assertEqual(
            with_parameters.command_id,
            sr920.SR920CommandId.READ_CONFIG_REQUEST,
        )
        self.assertEqual(
            with_parameters.parameters,
            {
                "config_id": sr920.SR920ConfigId.TX_POWER,
            },
        )

        wo_parameter = sr920.SR920Command(sr920.SR920CommandId.SAVE_CONFIG_REQUEST)

        self.assertEqual(
            wo_parameter.command_id,
            sr920.SR920CommandId.SAVE_CONFIG_REQUEST,
        )
        self.assertEqual(
            wo_parameter.parameters,
            {},
        )

    def test_to_bytes(self):
        for command in self.commands:
            if command["command"].command_id.name.endswith("REQUEST"):
                with self.subTest(command["command"]):
                    self.assertEqual(command["command"].to_bytes(), command["bytes"])

    def test_to_bytes_exc(self):
        missing_parameter = sr920.SR920Command(sr920.SR920CommandId.READ_CONFIG_REQUEST)

        with self.assertRaises(AttributeError):
            missing_parameter.to_bytes()

        invalid_parameter = sr920.SR920Command(
            sr920.SR920CommandId.READ_CONFIG_REQUEST,
            {"config_id": "TX_POWER"},
        )

        with self.assertRaises(AttributeError):
            invalid_parameter.to_bytes()

    def test_parse(self):
        for command in self.commands:
            if not command["command"].command_id.name.endswith("REQUEST"):
                with self.subTest(command["bytes"]):
                    parsed = sr920.SR920Command.parse(command["bytes"])

                    self.assertEqual(parsed.command_id, command["command"].command_id)
                    self.assertEqual(parsed.parameters, command["command"].parameters)

    def test_parse_exc(self):
        # invalid command_id
        with self.assertRaises(TypeError):
            sr920.SR920Command.parse("\xff\xff")

        # missing parameter
        with self.assertRaises(TypeError):
            sr920.SR920Command.parse("\x07\x80")

        # invalid parameter value
        with self.assertRaises(TypeError):
            sr920.SR920Command.parse("\x07\x80\xff")
