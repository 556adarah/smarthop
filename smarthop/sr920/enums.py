"""Definitions of enumulations for the OKI SmartHop SR module API command."""

import enum


class SR920CommandId(enum.Enum):
    """Represents an identifier of the API command."""

    READ_CONFIG_REQUEST = 0x0780
    READ_CONFIG_RESPONSE = 0x0781
    WRITE_CONFIG_REQUEST = 0x0782
    WRITE_CONFIG_RESPONSE = 0x0783
    SAVE_CONFIG_REQUEST = 0x0784
    SAVE_CONFIG_RESPONSE = 0x0785
    RESET_CONFIG_REQUEST = 0x0786
    RESET_CONFIG_RESPONSE = 0x0787
    SEND_DATA_REQUEST = 0x07A0
    SEND_DATA_RESPONSE = 0x07A1
    DATA_RECEIVED_NOTIFICATION = 0x07A2
    WRITE_RAM_CONFIG_REQUEST = 0x07A3
    WRITE_RAM_CONFIG_RESPONSE = 0x07A4
    READ_RAM_CONFIG_REQUEST = 0x07A5
    READ_RAM_CONFIG_RESPONSE = 0x07A6
    START_NETWORK_REQUEST = 0x07A7
    START_NETWORK_RESPONSE = 0x07A8
    NETWORK_STATE_CHANGED_NOTIFICATION = 0x07A9
    RESET_REQUEST = 0x07F0
    RESET_RESPONSE = 0x07F1
    SET_TIME_REQUEST = 0x07F2
    SET_TIME_RESPONSE = 0x07F3
    GET_TIME_REQUEST = 0x07F4
    GET_TIME_RESPONSE = 0x07F5
    GET_VERSION_REQUEST = 0x07FA
    GET_VERSION_RESPONSE = 0x07FB
    GET_NODE_LIST_REQUEST = 0x0330
    GET_NODE_LIST_RESPONSE = 0x0331
    GET_LINK_LIST_REQUEST = 0x0332
    GET_LINK_LIST_RESPONSE = 0x0333
    GET_ROUTE_REQUEST = 0x0334
    GET_ROUTE_RESPONSE = 0x0335
    MEASURE_RTT_REQUEST = 0x0336
    MEASURE_RTT_RESPONSE = 0x0337
    GET_NEIGHBOR_INFO_REQUEST = 0x0338
    GET_NEIGHBOR_INFO_RESPONSE = 0x0339
    CONTROL_FIXED_ADDRESS_REQUEST = 0x0340
    CONTROL_FIXED_ADDRESS_RESPONSE = 0x0341
    MEASURE_RADIO_STATUS_REQUEST = 0x0342
    MEASURE_RADIO_STATUS_RESPONSE = 0x0343
    UPDATE_FIRMWARE_REQUEST = 0x0742
    UPDATE_FIRMWARE_RESPONSE = 0x0743
    GET_MY_NEIGHBOR_INFO_REQUEST = 0x0744
    GET_MY_NEIGHBOR_INFO_RESPONSE = 0x0745
    GET_NETWORK_ADDRESS_REQUEST = 0x07F6
    GET_NETWORK_ADDRESS_RESPONSE = 0x07F7
    SCAN_CHANNEL_REQUEST = 0x0709
    SCAN_CHANNEL_RESPONSE = 0x070A


class SR920ConfigId(enum.Enum):
    """Represents an identifier of the configuration."""

    TX_POWER = 0x02
    MAC_ADDRESS = 0x12
    ASYNC_FALLBACK_COUNT = 0x22
    LED = 0x30
    DUMMY_SIZE = 0x31
    PARENT_SELECTION_MODE = 0xA2
    ENABLE_ENCRYPTION = 0xA6
    AUTO_START = 0xA7
    MAC_RETRY_COUNT = 0xA9
    NODE_TYPE = 0xB1
    NETWORK_ADDRESS = 0xB2
    HELLO_INTERVAL = 0xB3
    RREC_INTERVAL = 0xB4
    UPLINK_RETRY = 0xB5
    DOWNLINK_RETRY = 0xB6
    SLEEP_INTERVAL = 0xBB
    UPLINK_STATISTICS = 0xBC
    DOWNLINK_STATISTICS = 0xBD
    RREC_STATISTICS = 0xBE
    HELLO_STATISTICS = 0xBF
    PREFERRED_PARENT_NODE = 0xC1
    DELETE_UNREACHABLE_NEIGHBOR_INFO = 0xC2
    CHANNEL = 0xC5
    PAN_ID = 0xC6
    ENCRYPTION_KEY = 0xC7
    HELLO_REQUEST_INTERVAL = 0xC9
    ROUTE_EXPIRED = 0xD1
    KEY_RENEWAL_INTERVAL = 0xD4
    TIME_SYNC = 0xF0
    ENABLE_DATA_ENCRYPTION = 0xF3


class SR920NetworkMode(enum.Enum):
    """Represents a network mode used in the START_NETWORK_REQUEST/RESPONSE command."""

    START_NETWORK = 0x04
    START_CHANNEL_SCAN = 0x0A
    STOP_CHANNEL_SCAN = 0x0B


class SR920NetworkState(enum.Enum):
    """Represents a network state used in the NETWORK_STATE_CHANGED_NOTIFICATION command."""

    ADDRESS_CHANGED = 0x00
    MODULE_INITIALIZED = 0x02
    NODE_CONNECTED = 0x03
    NODE_DISCONNECTED = 0x04


class SR920NodeListType(enum.Enum):
    """Represents a type of node list used in the GET_NODE_LIST_REQUEST/RESPONSE command."""

    FIXED_ADDRESS = 0x00
    DYNAMIC_ADDRESS = 0x01
    CONNECTED = 0x02


class SR920FixedAddressControlMode(enum.Enum):
    """Represents a mode to control fixed address list used in the
    CONTROL_FIXED_ADDRESS_REQUEST/RESPONSE command."""

    ADD = 0x01
    REMOVE = 0x02
    SAVE = 0x03
    IMPORT = 0x04


class SR920TxPower(enum.Enum):
    """Represents a transmission power in the TX_POWER configuration."""

    TX_1mW = 0x01
    TX_20mW = 0x02


class SR920NodeType(enum.Enum):
    """Represents a node type used in the NODE_TYPE configuration."""

    COORDINATOR = 0x00
    ROUTER = 0x02
    SLEEP_COORDINATOR = 0x04
    SLEEP_ROUTER = 0x03

    def is_coordinator(self):
        """Returns True if current node type is a coordinator, otherwise False."""

        return self in (SR920NodeType.COORDINATOR, SR920NodeType.SLEEP_COORDINATOR)

    def is_router(self):
        """Returns True if current node type is a router, otherwise False."""

        return not self.is_coordinator()


class SR920OperationMode(enum.Enum):
    """Represents an operation mode of the module."""

    POWER_SAVING = 0x01
    BALANCE = 0x02
    LOW_LATENCY = 0x03
    NON_SLEEP = 0x04
