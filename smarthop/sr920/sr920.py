"""Definition of a class for the OKI SmartHop SR module API wrapper."""

import contextlib
import json
import logging
import math
import pkgutil
import threading
import time

import jsonschema
import serial
import tqdm

from serial import threaded

from smarthop import sr920
from smarthop.sr920 import protocol

_logger = logging.getLogger(__name__)


class SR920(contextlib.AbstractContextManager):
    """Represents the OKI SmartHop SR module API wrappper.

    Args:
        port: Device name or None.
            The serial port is opened on object creation if port is
            specified, otherwise to call open() are required.

    Examples:
        >>> # import smarthop.sr920 package
        >>> from smarthop import sr920

        >>> # create an instance with the specified serial port
        >>> sr=sr920.SR920("/dev/ttyS4")
        >>> sr.version
        'SRMP.02.02.0005'
        >>> sr.close()

        >>> # create an instance without any serial port
        >>> sr=sr920.SR920()
        >>> sr.open("/dev/ttyS4")
        >>> sr.version
        'SRMP.02.02.0005'
        >>> sr.close()

        >>> # or you can use the 'with' statement
        >>> with sr920.SR920("/dev/ttyS4") as sr:
        ...     sr.version
        ...
        'SRMP.02.02.0005'
    """

    def __init__(self, port=None):
        _logger.debug("enter __init__(): port=%s", port)

        self._serial = None
        self._reader = None
        self._protocol = None

        self._received_commands = []
        self._received_commands_lock = threading.Lock()

        self._notification_handler = None

        self._mac_address = None
        self._version = None

        self._measurement = None
        self._measurement_completed = threading.Event()
        self._measurement_lock = threading.Lock()

        if port:
            self.open(port)

    # overrides contextlib.AbstractContextManager.__exit__()
    def __exit__(self, exc_type, exc_value, traceback):
        _logger.debug(
            "enter __exit__(): exc_type=%s, exc_value=%s, traceback=%s",
            exc_type,
            exc_value,
            traceback,
        )

        self.close()

    @property
    def mac_address(self):
        """Gets a MAC address of the module."""

        if not self._mac_address:
            mac_address = self.read_config(sr920.SR920ConfigId.MAC_ADDRESS)

            if mac_address:
                self._mac_address = ":".join(
                    [mac_address[i : i + 2] for i in range(0, len(mac_address), 2)]
                )

        return self._mac_address

    @property
    def short_address(self):
        """Gets a short address assigned to the module."""

        address = self.get_network_address()

        if address and "short_address" in address:
            return address["short_address"]

        return "ffff"  # not connected

    @property
    def version(self):
        """Gets a firmware version of the module."""

        if not self._version:
            response = self.get_response(
                sr920.SR920Command(sr920.SR920CommandId.GET_VERSION_REQUEST)
            )

            if response and response.parameters["result"] == 0x00:
                version = response.parameters["version"]

                self._version = ".".join(
                    [version[0:4], version[4:6], version[6:8], version[8:]]
                )

        return self._version

    def open(self, port):
        """Opens the specified serial port.

        Args:
            port: Device name.
        """
        _logger.debug("enter open(): port=%s", port)

        self._serial = serial.Serial(port=port, baudrate=115200, timeout=1)

        self._reader = threaded.ReaderThread(self._serial, protocol.SR920Protocol)
        self._reader.start()

        self._protocol = self._reader.connect()[1]
        self._protocol.set_command_received_handler(self._on_command_received)

    def close(self):
        """Closes the serial port."""
        _logger.debug("enter close()")

        if self._serial:
            self._reader.close()

    def set_notification_handler(self, handler):
        """Sets a handler for the notification event.

        Args:
            handler: A handler for the notification event.
                A handler should be defined as follows:
                    def notification_handler(SR920Command)

        Examples:
            >>> from smarthop import sr920

            >>> # define the event handler
            >>> def on_notified(command):
            ...     print(command)
            ...

            >>> sr=sr920.SR920("/dev/ttyS4")

            >>> # add the event handler
            >>> sr.set_notification_handler(on_notified)

            >>> # receive NETWORK_STATE_CHANGED_NOTIFICATION: ADDRESS_CHANGED
            >>> sr.start()
            SR920Command: command_id=SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
            parameters={'state': <SR920NetworkState.ADDRESS_CHANGED: 0>,
            'short_address': '0001', 'pan_id': '0123', 'coordinator': 'ffff'}
            True
            >>> # note that 'coordinator_address' was used in v0.1 beta 1, instead of
            'coordinator'.

            >>> # receive NETWORK_STATE_CHANGED_NOTIFICATION: NODE_CONNECTED
            SR920Command: command_id=SR920CommandId.NETWORK_STATE_CHANGED_NOTIFICATION,
            parameters={'state': <SR920NetworkState.NODE_CONNECTED: 3>,
            'short_address': '0010', 'mac_address': '0000000000004567'}

            >>> # receive DATA_RECEIVED_NOTIFICATION
            SR920Command: command_id=SR920CommandId.DATA_RECEIVED_NOTIFICATION,
            parameters={'destination': '0001', 'source': '0010', 'nor': 3,
            'security': True, 'ttl': 30, 'data': bytearray(b'Hello, world!')}

            >>> sr.close()
        """
        _logger.debug("enter set_notification_handler(): handler=%s", handler)

        self._notification_handler = handler

    def get_response(self, request, retry=2, timeout=1):
        """Receives a response command by sending the specified request command.

        Args:
            request: An instance of the SR920Command class to send.
            retry: Retry count for sending a request command.
                Uses 2 times, if not specified.
            timeout: Waiting time for the response command received. (in seconds)
                Uses 1 second, if not specified.

        Returns:
            An instance of the SR920Command class representing a response command.
            Or returns None if any response is not received after retrying.
        """
        _logger.debug(
            "enter get_response(): request=%s, retry=%s, timeout=%s",
            request,
            retry,
            timeout,
        )

        request_id = request.command_id
        response_id = sr920.SR920CommandId(request_id.value + 1)

        with self._received_commands_lock:
            # remove old responses
            for command in self._received_commands:
                if command.command_id == response_id:
                    self._received_commands.remove(command)

        self._protocol.send_command(request)

        _logger.debug("waiting for response: %s", response_id)

        event_timeout = threading.Event()

        timer = threading.Timer(timeout, event_timeout.set)
        timer.start()

        while not event_timeout.wait(0.1):
            with self._received_commands_lock:
                for response in self._received_commands:
                    if response.command_id == response_id:
                        _logger.debug("response_id matched: %s", response_id)

                        if "seq_no" in response.parameters:
                            req_seq_no = request.parameters["seq_no"]
                            res_seq_no = response.parameters["seq_no"]

                            if req_seq_no == res_seq_no:
                                _logger.debug("seq_no matched: %s", res_seq_no)
                            else:
                                _logger.debug(
                                    "seq_no not matched: request=%s, response=%s",
                                    req_seq_no,
                                    res_seq_no,
                                )
                                continue

                        self._received_commands.remove(response)

                        return response

        if retry > 0:
            _logger.warning("request timed out. retrying...: %s", request)

            return self.get_response(request, retry - 1, timeout)

        _logger.error("request failed: %s", request)

        return None

    def read_config(self, config_id, read_from="ram"):
        """Reads a configuration value corresponding to the specified identifier.

        Args:
            config_id: An value of the SR920ConfigId enum.
            read_from: Configuration will be read from RAM if "ram" is specified,
                otherwise from Flash.

        Returns:
            An object representing a configuration value.
            Or returns None if configuration is not defined or command is failed.

        Examples:
            >>> # read a MAC address
            >>> sr.read_config(sr920.SR920ConfigId.MAC_ADDRESS)
            '0000000000000123'

            >>> # read a node type from flash
            >>> sr.read_config(sr920.SR920ConfigId.NODE_TYPE, read_from="flash")
            <SR920NodeType.COORDINATOR: 0>
        """
        _logger.debug(
            "enter read_config(): config_id=%s, read_from=%s",
            config_id,
            read_from,
        )

        request_id = (
            sr920.SR920CommandId.READ_RAM_CONFIG_REQUEST
            if read_from == "ram"
            else sr920.SR920CommandId.READ_CONFIG_REQUEST
        )
        parameters = {"config_id": config_id}

        response = self.get_response(sr920.SR920Command(request_id, parameters))

        if response and response.parameters["result"] == 0x00:
            return response.parameters["value"]

        return None

    def write_config(self, config_id, value, write_to="ram"):
        """Writes a configuration value corresponding to the specified identifier.

        Args:
            config_id: A value of the SR920ConfigId enum.
            value: An object representing a configuration value.
            write_to: Configuration will be written to RAM if "ram" is specified,
                otherwise to Flash.

        Returns:
            True if succeeded to write a configuration, otherwise False.

        Examples:
            >>> # configure the node type as SLEEP_ROUTER
            >>> sr.write_config(sr920.SR920ConfigId.NODE_TYPE,
            sr920.SR920NodeType.SLEEP_ROUTER)
            True

            >>> # enable auto start on Flash configuration
            >>> sr.write_config(sr920.SR920ConfigId.AUTO_START, True, write_to="flash")
            True
            >>> # require to save configurations when use Flash
            >>> sr.save_config()
            True
            >>> # reboot to reflect configurations
            >>> sr.reset()
            True
        """
        _logger.debug(
            "enter write_config(): config_id=%s, value=%s, write_to=%s",
            config_id,
            value,
            write_to,
        )

        request_id = (
            sr920.SR920CommandId.WRITE_RAM_CONFIG_REQUEST
            if write_to == "ram"
            else sr920.SR920CommandId.WRITE_CONFIG_REQUEST
        )
        parameters = {"config_id": config_id, "value": value}

        return self._simple_response(sr920.SR920Command(request_id, parameters))

    def save_config(self):
        """Saves configurations to Flash.

        Returns:
            True if succeeded to save configurations, otherwise False.
        """
        _logger.debug("enter save_config()")

        return self._simple_response(
            sr920.SR920Command(sr920.SR920CommandId.SAVE_CONFIG_REQUEST)
        )

    def reset_config(self):
        """Resets all configurations in Flash.

        Returns:
            True if succeeded to reset configurations, otherwise False.
        """
        _logger.debug("enter reset_config()")

        return self._simple_response(
            sr920.SR920Command(sr920.SR920CommandId.RESET_CONFIG_REQUEST)
        )

    def load_config(self, config_file, write_to="ram"):
        """Loads configurations from the specified configuration file.

        Args:
            config_file: A path to the configuration file.
            write_to: Configuration will be written to RAM if "ram" is specified,
                otherwise to Flash.

        Returns:
            True if succeeded to load configurations, otherwise False.

        Examples:
            >>> load configurations
            >>> sr.load_config("sr920_config.json")
            True

            >>> load configurations to Flash
            >>> sr.load_config("sr920_config.json", write_to="flash")
            True
            >>> # require to save and reboot when use Flash
            >>> sr.save_config()
            True
            >>> sr.reset()
            True
        """
        _logger.debug(
            "enter load_config(): config_file=%s, write_to=%s", config_file, write_to
        )

        with open(config_file) as fin:
            json_data = json.load(fin)

        json_schema = json.loads(
            pkgutil.get_data("smarthop", "schemas/sr920_config.schema.json")
        )

        try:
            jsonschema.validate(json_data, json_schema)
        except jsonschema.ValidationError as exc:
            _logger.error(
                "invalid configuration: [%s] %s",
                exc.path[0] if exc.path else "root",
                exc.message,
            )
            return False

        configs = {}

        for json_key in json_data:
            # ignore item started with $
            if json_key.startswith("$"):
                continue

            json_value = json_data[json_key]

            if json_key in ["NODE_TYPE", "TX_POWER"]:
                try:
                    config_id = sr920.SR920ConfigId[json_key]
                    config_value = (
                        sr920.SR920NodeType[json_value]
                        if json_key == "NODE_TYPE"
                        else sr920.SR920TxPower[json_value]
                    )

                    configs[config_id] = config_value
                except KeyError:
                    _logger.error("invalid value: %s", json_value)
                    return False
            elif json_key in ["ENABLE_TIME_SYNC", "OPERATION_MODE", "FIXED_ADDRESSES"]:
                configs[json_key] = json_value
            else:
                try:
                    config_id = sr920.SR920ConfigId[json_key]
                    config_value = json_value

                    configs[config_id] = config_value
                except KeyError:
                    _logger.error("invalid command_id: %s", json_key)
                    return False

        # operation mode configurations should be retrieved at last
        if "OPERATION_MODE" in configs:
            value = configs.pop("OPERATION_MODE")

            try:
                mode = sr920.SR920OperationMode[value]
            except KeyError:
                _logger.error("invalid value: %s", value)
                return False

            node_type = (
                configs[sr920.SR920ConfigId.NODE_TYPE]
                if sr920.SR920ConfigId.NODE_TYPE in configs
                else sr920.SR920NodeType.SLEEP_ROUTER
            )
            time_sync = (
                configs["ENABLE_TIME_SYNC"] if "ENABLE_TIME_SYNC" in configs else False
            )

            configs.update(
                SR920._get_operation_mode_configs(mode, node_type, time_sync)
            )

        # disable time sync
        if "ENABLE_TIME_SYNC" in configs:
            time_sync = configs.pop("ENABLE_TIME_SYNC")

            if not time_sync:
                configs[sr920.SR920ConfigId.TIME_SYNC] = {
                    "interval_unsync": 0,
                    "jitter_unsync": 0,
                    "interval_sync": 0,
                    "jitter_sync": 0,
                }

        _logger.debug("configs: %s", configs)

        # NODE_TYPE should be configured at first
        if sr920.SR920ConfigId.NODE_TYPE in configs:
            self.write_config(
                sr920.SR920ConfigId.NODE_TYPE,
                configs.pop(sr920.SR920ConfigId.NODE_TYPE),
                write_to,
            )

        if "FIXED_ADDRESSES" in configs:
            self.reset_fixed_address()

            fixed = configs.pop("FIXED_ADDRESSES")

            for short_address in fixed:
                self.add_fixed_address(short_address, fixed[short_address])

            self.save_fixed_address()

        for (config_id, config_value) in configs.items():
            self.write_config(config_id, config_value, write_to)

        return True

    def send_data(self, data, destination="0001", nor=3, security=True, ttl=30):
        """Sends the specified data with the specified conditions.

        Args:
            data: A bytes object to send.
            destination: A hexadecimal string representing a short address for
                the destination node.
                Uses "0001" that means the coordinator address, if not specified.
            nor: A value of NOR (Number of Retransmission).
                Uses 3 times, if not specified.
            security: True if security is on, otherwise False.
            ttl: A value of TTL (Time to Live).
                Uses 30 hops that equals to the maximum hop count, if not specified.

        Returns:
            True if succeeded to send data, otherwise False.
            Note that the arrival of data at the destination is not guaranteed.

        Examples:
            >>> # coordinator -> router 0010
            >>> sr.send_data(b"Hello, world!", destination="0010")
            True

            >>> # router -> coordination
            >>> sr.send_data(b"Hello, world!")
            True
        """
        _logger.debug(
            "enter send_data(): data=%s, destination=%s, nor=%s, security=%s, ttl=%s",
            data,
            destination,
            nor,
            security,
            ttl,
        )

        source = self.short_address

        if source == "ffff":
            _logger.warning("cancel to send data because network is disconnected")

            return False

        request_id = sr920.SR920CommandId.SEND_DATA_REQUEST
        parameters = {
            "destination": destination,
            "source": source,
            "nor": nor,
            "security": security,
            "ttl": ttl,
            "data": data,
        }

        return self._simple_response(
            sr920.SR920Command(request_id, parameters), timeout=10
        )

    def start(self, mode=None):
        """Starts network operation with the specified mode.

        Args:
            mode: A value of the SR920NetworkMode enum.
                Uses START_NETWORK, if not specified.

        Returns:
            True if succeeded to start network, otherwise False.
        """
        _logger.debug("enter start(): mode=%s", mode)

        request_id = sr920.SR920CommandId.START_NETWORK_REQUEST
        parameters = {"mode": mode if mode else sr920.SR920NetworkMode.START_NETWORK}

        response = self.get_response(sr920.SR920Command(request_id, parameters))

        if response and response.parameters["result"] in [0x00, 0x44]:
            if response.parameters["result"] == 0x44:
                _logger.warning("network already started")

            return True

        return False

    def reset(self):
        """Resets the module.

        Returns:
            True if succeeded to reset, otherwise False.
        """
        _logger.debug("enter reset()")

        return self._simple_response(
            sr920.SR920Command(sr920.SR920CommandId.RESET_REQUEST)
        )

    def get_time(self):
        """Gets the time from the module.

        Returns:
            A time in seconds since the epoch as float.
            Or returns None if failed.

        Examples:
            >>> # get time
            >>> tm = sr.get_time()
            >>> print(tm)
            1609459200.3423157

            >>> # convert to a datetime object
            >>> import datetime
            >>> dt = datetime.datetime.fromtimestamp(tm)
            >>> print(dt)
            2021-01-01 09:00:00.342316
        """
        _logger.debug("enter get_time()")

        response = self.get_response(
            sr920.SR920Command(sr920.SR920CommandId.GET_TIME_REQUEST)
        )

        if response and response.parameters["result"] == 0x00:
            time_sec = response.parameters["time_sec"]
            time_usec = response.parameters["time_usec"]

            time_got = time_sec + time_usec / 2 ** 32

            _logger.debug("time_got=%s", time_got)

            return time_got

        return None

    def set_time(self, time_to_set=None):
        """Sets the specified time to the module.

        Args:
            time_to_set: The time in seconds since the epoch as float.
                Uses current time by time.time(), if not specified.

        Returns:
            True if succeeded to set time, otherwise False.

        Examples:
            >>> # use current time
            >>> sr.set_time()
            True

            >>> import datetime
            >>> # 2021/01/01 09:00:00
            >>> dt = datetime.datetime(2021, 1, 1, 9, 0, 0)
            >>> # set the specified time
            >>> sr.set_time(dt.timestamp())
            True
        """
        _logger.debug("enter set_time(): time_to_set=%s", time_to_set)

        if not time_to_set:
            time_to_set = time.time()

        _logger.debug("time_to_set=%s", time_to_set)

        request_id = sr920.SR920CommandId.SET_TIME_REQUEST

        time_sec = math.floor(time_to_set)
        time_usec = math.floor((time_to_set - time_sec) * 2 ** 32)

        parameters = {
            "time_sec": time_sec,
            "time_usec": time_usec,
        }

        return self._simple_response(sr920.SR920Command(request_id, parameters))

    def get_node_list(self, list_type, seq_no=1):
        """Gets a list of node information.

        Args:
            list_type: A value of the SR920NodeListType enum.
            seq_no: A sequence number.
                Should not specify any value by user.

        Returns:
            A list object containing the node information.
            Or returns None if failed to get.

        Examples:
            >>> # 2 routers connected
            >>> sr.get_node_list(sr920.SR920NodeListType.CONNECTED)
            [{'short_address': '0010', 'mac_address': '0000000000004567'},
            {'short_address': 'abcd', 'mac_address': '00000000000089ab'}]

            >>> # 2 routers (including 1 router not connected) listed in fixed address
            >>> # list
            >>> sr.get_node_list(sr920.SR920NodeListType.FIXED_ADDRESS)
            [{'short_address': '0010', 'mac_address': '0000000000004567'},
            {'short_address': '0011', 'mac_address': '000000000000cdef'}]

            >>> # 1 router listed in dynamic address list
            >>> sr.get_node_list(sr920.SR920NodeListType.DYNAMIC_ADDRESS)
            [{'short_address': 'abcd', 'mac_address': '00000000000089ab'}]
        """
        _logger.debug(
            "enter get_node_list(): list_type=%s, seq_no=%s", list_type, seq_no
        )

        request_id = sr920.SR920CommandId.GET_NODE_LIST_REQUEST
        parameters = {"list_type": list_type, "seq_no": seq_no}

        response = self.get_response(sr920.SR920Command(request_id, parameters))

        if response:
            result = response.parameters["result"]

            if result in [0x00, 0x01]:
                node_list = response.parameters["node_list"]

                if result == 0x01:
                    node_list.extend(self.get_node_list(list_type, seq_no + 1))

                return node_list

        return None

    def get_link_list(self, seq_no=1):
        """Gets a list of link information.

        Args:
            seq_no: A sequence number.
                Should not specify any value by user.

        Returns:
            A list object containing the link information that consists of short
            address pair for the child/parent nodes.
            Or returns None if failed to get.

        Examples:
            >>> # In case the network topology is as follows:
            >>> #     0001 --+-- abcd --+-- 0010
            >>> #            |
            >>> #            +-- 0011
            >>> sr.get_link_list()
            [{'child': '0010', 'parent': 'abcd'}, {'child': '0011', 'parent': '0001'},
            {'child': 'abcd', 'parent': '0001'}]
        """
        _logger.debug("enter get_link_list(): seq_no=%s", seq_no)

        request_id = sr920.SR920CommandId.GET_LINK_LIST_REQUEST
        parameters = {"seq_no": seq_no}

        response = self.get_response(sr920.SR920Command(request_id, parameters))

        if response:
            result = response.parameters["result"]

            if result in [0x00, 0x01]:
                link_list = response.parameters["link_list"]

                if result == 0x01:
                    link_list.extend(self.get_link_list(seq_no + 1))

                return link_list

        return None

    def get_route(self, target):
        """Gets a route information to the specified node.

        Args:
            target: A hexadecimal string representing a short address of the target
                node.

        Returns:
            A list object representing the route information that consists of short
            addresses from the target node to the coordinator.
            Or returns None if failed to get.

        Examples:
            >>> # In case the network topology is as follows:
            >>> #     0001 --+-- abcd --+-- 0010
            >>> #            |
            >>> #            +-- 0011
            >>> sr.get_route("0010")
            ['0010', 'abcd', '0001']
            >>> sr.get_route("0011")
            ['0011', '0001']
            >>> sr.get_route("abcd")
            ['abcd', '0001']
        """
        _logger.debug("enter check_route(): target=%s", target)

        request_id = sr920.SR920CommandId.GET_ROUTE_REQUEST
        parameters = {"target": target}

        response = self.get_response(sr920.SR920Command(request_id, parameters))

        if response and response.parameters["result"] == 0x00:
            return response.parameters["route_info"]

        return None

    def measure_rtt(self, target, length=32):
        """Gets the result of RTT measurement with the specified node.

        Args:
            target: A hexadecimal string representing a short address of the target
                node.
            length: A data length to send. (in bytes)
                Uses 32 bytes length, if not specified.

        Returns:
            An object containing RTT, hop count and voltage.
            Or returns None if failed to measure.

        Examples:
            >>> # RTT: 0.125sec, hop count: 1, voltage: 3.21V
            >>> sr.measure_rtt("0011")
            {'rtt': 0.125, 'hop': 1, 'voltage': 3.21}
        """
        _logger.debug("enter measure_rtt(): target=%s, length=%s", target, length)

        request_id = sr920.SR920CommandId.MEASURE_RTT_REQUEST
        parameters = {"target": target, "length": length}

        response = self.get_response(
            sr920.SR920Command(request_id, parameters),
            timeout=self._get_timeout(target),
        )

        if response and response.parameters["result"] == 0x00:
            return {
                "rtt": response.parameters["rtt"] * 0.001,
                "hop": response.parameters["hop"],
                "voltage": response.parameters["voltage"] * 0.01,
            }

        return None

    def get_neighbor_info(self, target=None):
        """Gets a list of neighbor information of the specified node or the module
        itself.

        Args:
            target: A hexadecimal string representing a short address of the target
                node.
                Should not specify any value, if the module is a router, then neighbor
                information of the module itself will be returned.

        Returns:
            A list object containing the neighbor information.
            Or returns None if failed to get.

        Examples:
            >>> # coordinator
            >>> sr.get_neighbor_info("0011")
            [{'short_address': '0001', 'rssi': -21, 'link_cost': 1,
            'hello': bytearray(b'\xff')}, {'short_address': 'abcd', 'rssi': -42,
            'link_cost': 1, 'hello': bytearray(b'\xff')}]

            >>> # router
            >>> sr.get_neighbor_info()
            [{'short_address': '0001', 'rssi': -21, 'hop': 0, 'parent': 'ffff'},
            {'short_address': 'abcd', 'rssi': -42, 'hop': 2, 'parent': '0001'}]
        """
        _logger.debug("enter get_neighbor_info(): target=%s", target)

        if target:
            request_id = sr920.SR920CommandId.GET_NEIGHBOR_INFO_REQUEST
            parameters = {"target": target}
            timeout = self._get_timeout(target)
        else:
            request_id = sr920.SR920CommandId.GET_MY_NEIGHBOR_INFO_REQUEST
            parameters = {}
            timeout = 1

        response = self.get_response(
            sr920.SR920Command(request_id, parameters), timeout=timeout
        )

        if response and response.parameters["result"] == 0x00:
            return response.parameters["neighbor_list"]

        return None

    def control_fixed_address(self, mode, short_address=None, mac_address=None):
        """Controls the fixed address list.

        Args:
            mode: A value of the SR920FixedAddressControlMode enum.
            short_address: A hexadecimal string representing a short address.
                Required only when mode is ADD.
            mac_address: A hexadecimal string representing a MAC address.
                Not required when mode is SAVE or IMPORT.

        Returns:
            True if succeeded to control, otherwise False.

        Examples:
            >>> # add
            >>> sr.control_fixed_address(sr920.SR920FixedAddressControlMode.ADD,
            short_address="0011", mac_address="000000000000cdef")
            True

            >>> # remove
            >>> sr.control_fixed_address(sr920.SR920FixedAddressControlMode.REMOVE,
            mac_address="000000000000cdef")
            True

            >>> # save
            >>> sr.control_fixed_address(sr920.SR920FixedAddressControlMode.SAVE)
            True

            >>> # import from dynamic address list
            >>> sr.control_fixed_address(sr920.SR920FixedAddressControlMode.IMPORT)
            True
        """
        _logger.debug(
            "enter control_fixed_address(): mode=%s, short_address=%s, mac_address=%s",
            mode,
            short_address,
            mac_address,
        )

        request_id = sr920.SR920CommandId.CONTROL_FIXED_ADDRESS_REQUEST
        parameters = {
            "mode": mode,
            "short_address": short_address or "0000",
            "mac_address": mac_address or "0000000000000000",
        }

        return self._simple_response(sr920.SR920Command(request_id, parameters))

    def add_fixed_address(self, short_address, mac_address):
        """Provides a shortcut of the control_fixed_address method which mode is ADD.

        Args:
            short_address: A hexadecimal string representing a short address.
            mac_address: A hexadecimal string representing a MAC address.

        Returns:
            True if succeeded to add, otherwise False.

        Examples:
            >>> sr.add_fixed_address("0011", "000000000000cdef")
            True
            >>> # require to save
            >>> sr.save_fixed_address()
            True
        """
        _logger.debug(
            "enter add_fixed_address(): short_address=%s, mac_address=%s",
            short_address,
            mac_address,
        )

        return self.control_fixed_address(
            sr920.SR920FixedAddressControlMode.ADD,
            short_address=short_address,
            mac_address=mac_address,
        )

    def remove_fixed_address(self, mac_address):
        """Provides a shortcut of the control_fixed_address method which mode is REMOVE.

        Args:
            mac_address: A hexadecimal string representing a MAC address.

        Returns:
            True if succeeded to remove, otherwise False.

        Examples:
            >>> sr.remove_fixed_address("000000000000cdef")
            True
            >>> # require to save
            >>> sr.save_fixed_address()
            True
        """
        _logger.debug("enter remove_fixed_address(): mac_address=%s", mac_address)

        return self.control_fixed_address(
            sr920.SR920FixedAddressControlMode.REMOVE,
            mac_address=mac_address,
        )

    def save_fixed_address(self):
        """Provides a shortcut of the control_fixed_address method which mode is SAVE.

        Returns:
            True if succeeded to save, otherwise False.
        """
        _logger.debug("enter save_fixed_address()")

        return self.control_fixed_address(sr920.SR920FixedAddressControlMode.SAVE)

    def import_fixed_address(self):
        """Provides a shortcut of the control_fixed_address method which mode is IMPORT.

        Returns:
            True if succeeded to import, otherwise False.
        """
        _logger.debug("enter import_fixed_address()")

        return self.control_fixed_address(sr920.SR920FixedAddressControlMode.IMPORT)

    def reset_fixed_address(self):
        """Removes all addresses from the fixed address list.

        Returns:
            True if succeeded to reset, otherwise False.

        Examples:
            >>> sr.reset_fixed_address()
            True
            >>> # require to save
            >>> sr.save_fixed_address()
            True
        """
        _logger.debug("enter reset_fixed_address()")

        node_list = self.get_node_list(sr920.SR920NodeListType.FIXED_ADDRESS)

        if not node_list:
            return False

        for node in node_list:
            self.remove_fixed_address(node["mac_address"])

        return True

    def start_radio_measurement(
        self, destinations=None, source="0001", count=100, interval=4000, length=32
    ):
        """Starts radio status measurement with the specified conditions.

        Args:
            destinations: A list object containing a hexadecimal string representing
                a short address.
                Uses all connected nodes excepting for source, if not specified.
            source: A hexadecimal string representing a short address for
                the source node.
                Uses "0001" that means the coordinator address, if not specified.
            count: Number of sending test packets.
                Uses 100 times, if not specified.
            interval: Interval to send test packets. (in milli-seconds)
                Uses 4 seconds, if not specified.
            length: A data length to send. (in bytes)
                Uses 32 bytes length, if not specified.

        Returns:
            An instance of the threading.Event class representing the event when
            the measurement is completed.
            Or returns None if failed to start measurement.

        Examples:
            >>> # require to start network
            >>> sr.start()
            True

            >>> # start measurement
            >>> completed = sr.start_radio_measurement()

            >>> # waiting for complete of measurement
            >>> while not completed.wait(1):
            ...     pass
            ...

            >>> # get all result of measurement
            >>> sr.get_result_radio_measurement()
            [{'destination': '0010', 'rssi_max': -53, 'rssi_min': -56,
            'rssi_ave': -53.87, 'per': 0.0}, {'destination': '0011',
            'rssi_max': -48, 'rssi_min': -50, 'rssi_ave': -48.53, 'per': 0.0}]

            >>> # or get partial result of measurement
            >>> sr.get_result_radio_measurement(["0010"])
            [{'destination': '0010', 'rssi_max': -53, 'rssi_min': -56,
            'rssi_ave': -53.87, 'per': 0.0}]
        """
        _logger.debug(
            "enter start_radio_measurement(): "
            "destinations=%s, source=%s, count=%s, interval=%s, length=%s",
            destinations,
            source,
            count,
            interval,
            length,
        )

        if not destinations:
            node_list = self.get_node_list(sr920.SR920NodeListType.CONNECTED)

            if not node_list:
                _logger.error("failed to get node list")
                return None

            destinations = [node["short_address"] for node in node_list]

            if source in destinations:
                destinations.remove(source)
                destinations.append("0001")

            _logger.debug("destinations: %s", destinations)

        command_id = sr920.SR920CommandId.MEASURE_RADIO_STATUS_REQUEST

        for destination in destinations:
            parameters = {
                "mode": sr920.SR920RadioMeasurementMode.START_RECEIVE,
                "target": destination,
            }

            if not self._simple_response(
                sr920.SR920Command(command_id, parameters),
                timeout=self._get_timeout(destination),
            ):
                _logger.error("failed to start receiving: %s", destination)
                return None

        parameters = {
            "mode": sr920.SR920RadioMeasurementMode.START_SEND,
            "target": source,
            "count": count,
            "interval": interval,
            "length": length,
        }

        if not self._simple_response(
            sr920.SR920Command(command_id, parameters),
            timeout=self._get_timeout(source),
        ):
            _logger.error("failed to start sending: %s", source)
            return None

        self._measurement_completed.clear()

        self._measurement = {
            "destinations": destinations,
            "source": source,
            "count": count,
            "interval": interval,
            "length": length,
            "start": time.time(),
            "worker": threading.Thread(
                target=self._measurement_worker, name="measurement"
            ),
        }

        self._measurement["worker"].start()

        return self._measurement_completed

    def get_result_radio_measurement(self, destinations=None):
        """Get results of radio status measurement.

        Args:
            destinations: A list object containing a hexadecimal string representing
                a short address.
                Uses all nodes to measure, if not specified.

        Returns:
            A list object containing the measurement result for each node.
            Or returns None if failed to get result.
        """
        _logger.debug(
            "enter get_result_radio_measurement(): destinations=%s", destinations
        )

        if not self._measurement:
            _logger.error("measurement not started or aborted")
            return None

        if not destinations:
            destinations = self._measurement["destinations"]

        if self._measurement["worker"].is_alive():
            _logger.warning("measurement not completed. waiting for the complete")
            self._measurement["worker"].join()

        results = []

        command_id = sr920.SR920CommandId.MEASURE_RADIO_STATUS_REQUEST

        for destination in destinations:
            if destination not in self._measurement["destinations"]:
                _logger.warning("measurement not started on target: %s", destination)
                continue

            parameters = {
                "mode": sr920.SR920RadioMeasurementMode.RESULT,
                "target": destination,
            }

            response = self.get_response(
                sr920.SR920Command(command_id, parameters),
                timeout=self._get_timeout(destination),
            )

            if not response or response.parameters["result"] != 0x00:
                _logger.warning("failed to get measurement result: %s", destination)
                continue

            rssi_ave = (
                response.parameters["rssi_ave_int"]
                + response.parameters["rssi_ave_frac"] * -0.01
            )
            count = self._measurement["count_sent"]
            per = (count - response.parameters["count"]) / count

            results.append(
                {
                    "destination": destination,
                    "rssi_max": response.parameters["rssi_max"],
                    "rssi_min": response.parameters["rssi_min"],
                    "rssi_ave": rssi_ave,
                    "per": per,
                }
            )

        return results

    def abort_radio_measurement(self):
        """Aborts radio status measurement.

        Returns:
            True if succeeded to abort measurement, otherwise False.

        Examples:
            >>> # require to start network
            >>> sr.start()
            True

            >>> # start measurement
            >>> completed = sr.start_radio_measurement()

            >>> # abort measurement
            >>> sr.abort_radio_measurement()
            True
        """
        _logger.debug("enter abort_radio_measurement()")

        with self._measurement_lock:
            if not self._measurement:
                _logger.error("measurement not started")
                return False

            if "end" in self._measurement:
                _logger.warning("measurement already completed")
                return True

            source = self._measurement["source"]

        command_id = sr920.SR920CommandId.MEASURE_RADIO_STATUS_REQUEST
        parameters = {
            "mode": sr920.SR920RadioMeasurementMode.ABORT,
            "target": source,
        }

        if self._simple_response(
            sr920.SR920Command(command_id, parameters),
            timeout=self._get_timeout(source),
        ):
            with self._measurement_lock:
                self._measurement = None

            _logger.info("measurement aborted by user")

            return True

        return False

    def update(self, firmware_file, force=False):
        """Updates firmware of the module.

        Args:
            firmware_file: A path to the firmware file.
            force: Fails update when the specified firmware is older than or equals to
            current version, if False. Otherwise force update without version check.

        Returns:
            True if succeeded to update, otherwise False.

        Examples:
            >>> sr.update("SRMP_rev02020005.dat")
            writing: 100%|████████████████████████| 149/149 [00:38<00:00,  3.86frames/s]
            True
        """
        _logger.debug("enter update(): firmware_file=%s", firmware_file)

        command_id = sr920.SR920CommandId.UPDATE_FIRMWARE_REQUEST
        seq_no = -1

        def next_seq_no():
            nonlocal seq_no

            seq_no = (seq_no + 1) % 65536

            return seq_no

        def get_version():
            parameters = {
                "sub_command_id": sr920.SR920FirmwareUpdateCommandId.GET_VERSION,
                "seq_no": next_seq_no(),
            }

            response = self.get_response(
                sr920.SR920Command(command_id, parameters),
                timeout=2,  # work around: first response too late
            )

            if not response or response.parameters["status"] != 0x00:
                return None

            return response.parameters["version"]

        # read firmware
        with open(firmware_file, mode="rb") as fin:
            firmware_bin = fin.read()

        if len(firmware_bin) < 16:
            _logger.error("firmware size too short")

            return False

        data = firmware_bin[:-16]
        checksum = firmware_bin[-16:-14]
        version = firmware_bin[-12:].decode("ascii")

        _logger.debug("checksum=%s, version=%s", checksum, version)

        if not force:
            # get version
            version_current = get_version()

            if not version_current:
                _logger.error("failed to get current version")

                return False

            # check version
            if version <= version_current:
                _logger.error(
                    "firmware is older than or equals to current version: "
                    "firmware=%s, current=%s",
                    version,
                    version_current,
                )

                return False

        # start update
        parameters = {
            "sub_command_id": sr920.SR920FirmwareUpdateCommandId.START,
            "seq_no": next_seq_no(),
            "version": version,
            "size": len(data),
            "checksum": checksum,
        }

        response = self.get_response(
            sr920.SR920Command(command_id, parameters),
            timeout=2,  # work around: first response too late
        )

        if not response or response.parameters["status"] != 0x00:
            _logger.error("failed to start firmware update")

            return False

        # write firmware
        page_no = 0

        for i in tqdm.trange(0, len(data), 1024, desc="writing", unit="frames"):
            frame_total = i // 1024

            page_no = frame_total // 64
            frame_no = frame_total % 64

            frame = bytearray(data[i : i + 1024])

            if len(frame) < 1024:
                frame.extend(b"\xff" * (1024 - len(frame)))

            parameters = {
                "sub_command_id": sr920.SR920FirmwareUpdateCommandId.WRITE,
                "seq_no": next_seq_no(),
                "page_no": page_no,
                "frame_no": frame_no,
                "frame": frame,
            }

            response = self.get_response(sr920.SR920Command(command_id, parameters))

            if not response or response.parameters["status"] != 0x00:
                _logger.error("failed to write firmware")

                return False

        # check result
        parameters = {
            "sub_command_id": sr920.SR920FirmwareUpdateCommandId.CHECK,
            "seq_no": next_seq_no(),
            "last_page": page_no,
        }

        response = self.get_response(sr920.SR920Command(command_id, parameters))

        if not response or response.parameters["status"] != 0x00:
            _logger.error("failed to check result of update")

            return False

        # reset
        parameters = {
            "sub_command_id": sr920.SR920FirmwareUpdateCommandId.RESET,
            "seq_no": next_seq_no(),
            "wait": 1,
        }

        response = self.get_response(sr920.SR920Command(command_id, parameters))

        if not response or response.parameters["status"] != 0x00:
            _logger.error("failed to reset")

            return False

        # wait boot up
        time.sleep(5)

        # confirm version
        version_updated = get_version()

        if not version_updated or version != version_updated:
            _logger.error("failed to update")

            return False

        _logger.info("firmware updated: %s", version_updated)

        return True

    def get_network_address(self):
        """Gets network information related to the current network.

        Returns:
            A dict object containing short address, PAN ID and coordinator's short
            address.
            Or returns None if failed to get.

        Examples:
            >>> sr.get_network_address()
            {'short_address': '0001', 'pan_id': '0123', 'coordinator': 'ffff'}
            >>> # note that 'coordinator_address' was used in v0.1 beta 1, instead of
            'coordinator'.
        """
        _logger.debug("enter get_network_address()")

        response = self.get_response(
            sr920.SR920Command(sr920.SR920CommandId.GET_NETWORK_ADDRESS_REQUEST)
        )

        if response and response.parameters.pop("result") == 0x00:
            return response.parameters

        return None

    def scan_channels(self, channels=None, count=500, interval=2):
        """Scans noise level in the specified channels.

        Args:
            channels: A list object containing an int object between 33 and 60
                representing the channel to scan.
                Uses all channels, if not specified.
            count: Scan count.
                Uses 500 times, if not specified.
            interval: Scan interval in milli-seconds.
                Uses 2 msec, if not specified.

        Returns:
            A list object containing the scan result for each channel.

        Examples:
            >>> # configure as coordinator
            >>> sr.write_config(sr920.SR920ConfigId.NODE_TYPE,
            ... sr920.SR920NodeType.COORDINATOR)
            True
            >>> # start channel scan mode
            >>> sr.start(sr920.SR920NetworkMode.START_CHANNEL_SCAN)
            True

            >>> # scan all channels
            >>> sr.scan_channels()
            scanning: 100%|███████████████████████| 28/28 [00:32<00:00,  1.15s/channels]
            [{'channel': 33, 'rssi_max': -103, 'rssi_min': -123, 'rssi_ave': -113.65},
            {'channel': 34, 'rssi_max': -105, 'rssi_min': -123, 'rssi_ave': -113.79},
            ... (omitted)
            {'channel': 60, 'rssi_max': -107, 'rssi_min': -123, 'rssi_ave': -114.22}]

            >>> # scan specified channels
            >>> sr.scan_channels([33,34])
            scanning: 100%|█████████████████████████| 2/2 [00:02<00:00,  1.14s/channels]
            [{'channel': 33, 'rssi_max': -104, 'rssi_min': -123, 'rssi_ave': -114.03},
            {'channel': 34, 'rssi_max': -105, 'rssi_min': -123, 'rssi_ave': -113.92}]

            >>> # stop channel scan mode
            >>> sr.start(sr920.SR920NetworkMode.STOP_CHANNEL_SCAN)
            True
        """
        _logger.debug(
            "enter scan_channels(): channels=%s, count=%s, interval=%s",
            channels,
            count,
            interval,
        )

        results = []

        if not channels:
            channels = list(range(33, 61))

        for channel in tqdm.tqdm(channels, desc="scanning", unit="channels"):
            command_id = sr920.SR920CommandId.SCAN_CHANNEL_REQUEST
            parameters = {
                "mode": sr920.SR920ChannelScanMode.START,
                "channel": channel,
                "count": count,
                "interval": interval,
            }

            # timeout has 50% margins
            timeout = count * interval * 0.001 * 1.5

            response = self.get_response(
                sr920.SR920Command(command_id, parameters), timeout=timeout
            )

            if not response or response.parameters["result"] != 0x00:
                _logger.warning("failed to scan: channel=%s", channel)

                continue

            results.append(
                {
                    "channel": response.parameters["channel"],
                    "rssi_max": response.parameters["rssi_max"],
                    "rssi_min": response.parameters["rssi_min"],
                    "rssi_ave": response.parameters["rssi_ave"] * 0.01,
                }
            )

        return results

    def _on_command_received(self, cmd_received):
        _logger.debug("enter _on_command_received(): cmd_received=%s", cmd_received)

        if cmd_received.command_id.name.endswith("NOTIFICATION"):
            if self._notification_handler:
                self._notification_handler(cmd_received)
        else:
            with self._received_commands_lock:
                self._received_commands.append(cmd_received)

    def _simple_response(self, request, retry=2, timeout=1):
        _logger.debug(
            "enter _simple_response(): request=%s, retry=%s, timeout=%s",
            request,
            retry,
            timeout,
        )

        response = self.get_response(request, retry, timeout)

        if response and response.parameters["result"] == 0x00:
            return True

        return False

    def _get_timeout(self, target):
        _logger.debug("enter _get_timeout(): target=%s", target)

        # get hop count to the target
        hop = len(self.get_route(target)) - 1

        # timeout = (hop for round trip + 50% margins) or 1sec if target is coordinator
        timeout = (hop * 2 * 1.5) or 1

        return timeout

    def _measurement_worker(self):
        _logger.debug("enter _measurement_worker()")

        # timeout = (2 + interval) * count +50% margins
        timeout = (
            (2 + self._measurement["interval"] / 1000)
            * self._measurement["count"]
            * 1.5
        )

        event_timeout = threading.Event()

        timer = threading.Timer(timeout, event_timeout.set)
        timer.start()

        while not event_timeout.wait(0.1):
            with self._measurement_lock:
                # measurement aborted
                if not self._measurement:
                    break

                for command in self._received_commands:
                    if (
                        command.command_id
                        == sr920.SR920CommandId.MEASURE_RADIO_STATUS_RESPONSE
                        and command.parameters["mode"]
                        == sr920.SR920RadioMeasurementMode.RESULT
                    ):
                        self._measurement["end"] = time.time()
                        self._measurement["count_sent"] = command.parameters["count"]

                        _logger.info(
                            "measurement completed in %.2f sec",
                            self._measurement["end"] - self._measurement["start"],
                        )

                        break

                if "end" in self._measurement:
                    break
        else:
            with self._measurement_lock:
                self._measurement = None

            _logger.error("measurement timed out")

        self._measurement_completed.set()

    @staticmethod
    def _get_operation_mode_configs(mode, node_type, time_sync=False):
        _logger.debug(
            "enter _get_operation_mode_configs(): mode=%s, node_type=%s, time_sync=%s",
            mode,
            node_type,
            time_sync,
        )

        configs = None

        if mode == sr920.SR920OperationMode.POWER_SAVING:
            configs = {
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: "00",  # low speed
                sr920.SR920ConfigId.HELLO_INTERVAL: "4B",  # 3.7h
                sr920.SR920ConfigId.RREC_INTERVAL: "41",  # 51min
                sr920.SR920ConfigId.UPLINK_RETRY: 2,
                sr920.SR920ConfigId.DOWNLINK_RETRY: 2,
                sr920.SR920ConfigId.SLEEP_INTERVAL: 100,  # 2sec
                sr920.SR920ConfigId.HELLO_REQUEST_INTERVAL: 80,
                sr920.SR920ConfigId.ROUTE_EXPIRED: 12240000,  # 3.4h
                sr920.SR920ConfigId.TIME_SYNC: {
                    "interval_unsync": 3600,  # 1h
                    "jitter_unsync": 255,
                    "interval_sync": 36000,  # 10h
                    "jitter_sync": 255,
                },
            }
        elif mode == sr920.SR920OperationMode.BALANCE:
            configs = {
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: "00",  # low speed
                sr920.SR920ConfigId.HELLO_INTERVAL: "40",  # 34.1min
                sr920.SR920ConfigId.RREC_INTERVAL: "3F",  # 17.5min
                sr920.SR920ConfigId.UPLINK_RETRY: 2,
                sr920.SR920ConfigId.DOWNLINK_RETRY: 2,
                sr920.SR920ConfigId.SLEEP_INTERVAL: 25,  # 500msec
                sr920.SR920ConfigId.HELLO_REQUEST_INTERVAL: 15,
                sr920.SR920ConfigId.ROUTE_EXPIRED: 4320000,  # 1.2h
                sr920.SR920ConfigId.TIME_SYNC: {
                    "interval_unsync": 1800,  # 30min
                    "jitter_unsync": 255,
                    "interval_sync": 10800,  # 3h
                    "jitter_sync": 255,
                },
            }
        elif mode == sr920.SR920OperationMode.LOW_LATENCY:
            configs = {
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: "01",  # high speed
                sr920.SR920ConfigId.HELLO_INTERVAL: "30",  # 9.6min
                sr920.SR920ConfigId.RREC_INTERVAL: "2B",  # 7min
                sr920.SR920ConfigId.UPLINK_RETRY: 2,
                sr920.SR920ConfigId.DOWNLINK_RETRY: 2,
                sr920.SR920ConfigId.SLEEP_INTERVAL: 5,  # 100msec
                sr920.SR920ConfigId.HELLO_REQUEST_INTERVAL: 15,
                sr920.SR920ConfigId.ROUTE_EXPIRED: 1680000,  # 28min
                sr920.SR920ConfigId.TIME_SYNC: {
                    "interval_unsync": 600,  # 10min
                    "jitter_unsync": 180,
                    "interval_sync": 3600,  # 1h
                    "jitter_sync": 180,
                },
            }
        elif mode == sr920.SR920OperationMode.NON_SLEEP:
            configs = {
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: "01",  # high speed
                sr920.SR920ConfigId.HELLO_INTERVAL: "20",  # 1.1min
                sr920.SR920ConfigId.RREC_INTERVAL: "23",  # 2.6min
                sr920.SR920ConfigId.UPLINK_RETRY: 2,
                sr920.SR920ConfigId.DOWNLINK_RETRY: 2,
                sr920.SR920ConfigId.HELLO_REQUEST_INTERVAL: 15,
                sr920.SR920ConfigId.ROUTE_EXPIRED: 600000,  # 10min
                sr920.SR920ConfigId.TIME_SYNC: {
                    "interval_unsync": 10,
                    "jitter_unsync": 5,
                    "interval_sync": 10,
                    "jitter_sync": 30,
                },
            }

        if configs and node_type.is_router():
            del configs[sr920.SR920ConfigId.ROUTE_EXPIRED]

        if configs and not time_sync:
            del configs[sr920.SR920ConfigId.TIME_SYNC]

        return configs
