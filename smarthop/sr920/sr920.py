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

        self._notification_handler = None

        self._version = None

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
            'short_address': '0001', 'pan_id': '0123', 'coordinator_address': 'ffff'}
            True

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

        self._protocol.send_command(request)

        _logger.debug("waiting for response: %s", response_id)

        event_timeout = threading.Event()

        timer = threading.Timer(timeout, event_timeout.set)
        timer.start()

        while not event_timeout.wait(0.1):
            for response in self._received_commands:
                if response.command_id == response_id:
                    _logger.debug("response_id matched: %s", response_id)

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

        if response and response.parameters["result"] == 0:
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
            try:
                value = configs.pop("OPERATION_MODE")
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
                configs.pop("ENABLE_TIME_SYNC")
                if "ENABLE_TIME_SYNC" in configs
                else False
            )

            configs.update(
                SR920._get_operation_mode_configs(mode, node_type, time_sync)
            )

        _logger.debug("configs: %s", configs)

        # NODE_TYPE should be configured at first
        if sr920.SR920ConfigId.NODE_TYPE in configs:
            self.write_config(
                sr920.SR920ConfigId.NODE_TYPE,
                configs.pop(sr920.SR920ConfigId.NODE_TYPE),
                write_to,
            )

        if "FIXED_ADDRESSES" in configs:
            fixed = configs.pop("FIXED_ADDRESSES")

            for short_address in fixed:
                self.control_fixed_address(
                    sr920.SR920FixedAddressControlMode.ADD,
                    short_address=short_address,
                    mac_address=fixed[short_address],
                )

            self.control_fixed_address(sr920.SR920FixedAddressControlMode.SAVE)

        for config_id in configs:
            self.write_config(config_id, configs[config_id], write_to)

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
            sr920.SR920Command(request_id, parameters), timeout=2
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

        return self._simple_response(sr920.SR920Command(request_id, parameters))

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

    def measure_rtt(self, target, legnth=30):
        """Gets the result of RTT measurement with the specified node.

        Args:
            target: A hexadecimal string representing a short address of the target
                node.
            length: A data length to send. (in bytes)
                Uses 30 bytes length, if not specified.

        Returns:
            An object containing RTT, hop count and voltage.
            Or returns None if failed to measure.

        Examples:
            >>> # RTT: 0.125sec, hop count: 1, voltage: 3.21V
            >>> sr.measure_rtt("0011")
            {'rtt': 0.125, 'hop': 1, 'voltage': 3.21}
        """
        _logger.debug("enter measure_rtt(): target=%s, length=%s", target, legnth)

        request_id = sr920.SR920CommandId.MEASURE_RTT_REQUEST
        parameters = {"target": target, "length": legnth}

        response = self.get_response(
            sr920.SR920Command(request_id, parameters), timeout=2
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
        else:
            request_id = sr920.SR920CommandId.GET_MY_NEIGHBOR_INFO_REQUEST
            parameters = {}

        response = self.get_response(
            sr920.SR920Command(request_id, parameters), timeout=2
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

    def get_network_address(self):
        """Gets network information related to the current network.

        Returns:
            A dict object containing short address, PAN ID and coordinator's short
            address.
            Or returns None if failed to get.

        Examples:
            >>> sr.get_network_address()
            {'short_address': '0001', 'pan_id': '0123', 'coordinator_address': 'ffff'}
        """
        _logger.debug("enter get_network_address()")

        response = self.get_response(
            sr920.SR920Command(sr920.SR920CommandId.GET_NETWORK_ADDRESS_REQUEST)
        )

        if response and response.parameters.pop("result") == 0x00:
            return response.parameters

        return None

    def _on_command_received(self, cmd_received):
        _logger.debug("enter on_command_received(): cmd_received=%s", cmd_received)

        if cmd_received.command_id.name.endswith("NOTIFICATION"):
            if self._notification_handler:
                self._notification_handler(cmd_received)
        else:
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
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: b"\x00",  # low speed
                sr920.SR920ConfigId.HELLO_INTERVAL: b"\x4b",  # 3.7h
                sr920.SR920ConfigId.RREC_INTERVAL: b"\x41",  # 51min
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
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: b"\x00",  # low speed
                sr920.SR920ConfigId.HELLO_INTERVAL: b"\x40",  # 34.1min
                sr920.SR920ConfigId.RREC_INTERVAL: b"\x3f",  # 17.5min
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
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: b"\x01",  # high speed
                sr920.SR920ConfigId.HELLO_INTERVAL: b"\x30",  # 9.6min
                sr920.SR920ConfigId.RREC_INTERVAL: b"\x2b",  # 7min
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
                sr920.SR920ConfigId.PARENT_SELECTION_MODE: b"\x01",  # high speed
                sr920.SR920ConfigId.HELLO_INTERVAL: b"\x20",  # 1.1min
                sr920.SR920ConfigId.RREC_INTERVAL: b"\x23",  # 2.6min
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
            configs[sr920.SR920ConfigId.TIME_SYNC] = {
                "interval_unsync": 0,
                "jitter_unsync": 0,
                "interval_sync": 0,
                "jitter_sync": 0,
            }

        return configs
