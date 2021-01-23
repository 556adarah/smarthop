"""Definition of a class for the OKI SmartHop SR module API command."""

import enum
import json
import logging
import pkgutil

from smarthop import sr920

_logger = logging.getLogger(__name__)

_templates = json.loads(pkgutil.get_data("smarthop", "sr920/commands.json"))


class SR920Command:
    """Represents the OKI SmartHop SR module API command.

    Args:
        command_id: A value of the SR920CommandId enum.
        parameters: A dict object representing the API command parameters.
    """

    def __init__(self, command_id, parameters=None):
        _logger.debug(
            "enter __init__(): command_id=%s, parameters=%s", command_id, parameters
        )

        self._command_id = command_id
        self._parameters = parameters if parameters else {}

        self._template = None

    @property
    def command_id(self):
        """Gets an identifier of the API command."""

        return self._command_id

    @property
    def parameters(self):
        """Gets a dict object representing the API command parameters."""

        return self._parameters

    def to_bytes(self):
        """Converts to a bytes object representing the API command.

        Returns:
            A bytes object representing the API command.
        """
        _logger.debug("enter to_bytes()")

        command = bytearray(self.command_id.value.to_bytes(2, "big"))

        if not self._template:
            self._template = SR920Command._get_template(self.command_id)

        if self._template and "parameters" in self._template:
            command.extend(
                SR920Command._pack_parameters(
                    self.parameters, self._template["parameters"]
                )
            )

        return command

    @classmethod
    def parse(cls, data):
        """Converts the specified bytes object to an instance of the SR920Command class.

        Args:
            data: a bytes object to parse.

        Returns:
            An instance of the SR920Command class.
        """
        _logger.debug("enter parse(): data=%s", data)

        command_id = sr920.SR920CommandId(int.from_bytes(data[:2], byteorder="big"))
        parameters = {}

        payload = data[2:] if len(data) > 2 else None
        template = cls._get_template(command_id)

        if template and "parameters" in template:
            cls._unpack_parameters(parameters, payload, template["parameters"])

        return cls(command_id, parameters)

    @staticmethod
    def _get_template(command_id):
        _logger.debug("enter _get_template(): command_id=%s", command_id)

        for template in _templates["commands"]:
            if template["name"] == command_id.name:
                return template

        _logger.warning("command template not found: command_id=%s", command_id)

        return None

    @classmethod
    def _pack_parameters(cls, parameters, templates):
        _logger.debug(
            "enter _pack_parameters(): parameters=%s, templates=%s",
            parameters,
            templates,
        )

        data = bytearray()

        for template in templates:
            temp_type = template["type"]

            if temp_type.startswith("select:"):
                if temp_type[7:] not in parameters:
                    raise AttributeError(
                        "select variable not found: %s" % temp_type[7:]
                    )

                param_case = parameters[temp_type[7:]]

                # use name if select variable is an instance of Enum
                if isinstance(param_case, enum.Enum):
                    param_case = param_case.name

                default_case = None

                for temp_case in template["cases"]:
                    if "default" in temp_case:
                        default_case = temp_case["default"]
                    elif param_case in temp_case["case"]:
                        data.extend(
                            cls._pack_parameters(parameters, temp_case["parameters"])
                        )
                        default_case = None
                        break

                if default_case:
                    data.extend(cls._pack_parameters(parameters, default_case))

                continue

            if temp_type.startswith("ref:"):
                if temp_type[4:] not in _templates["definitions"]:
                    raise AttributeError("reference not found: %s" % temp_type[4:])

                reference = _templates["definitions"][temp_type[4:]]

                data.extend(cls._pack_parameters(parameters, reference))

                continue

            if "value" in template:
                param_value = template["value"]
            else:
                if template["name"] not in parameters:
                    raise AttributeError("parameter not found: %s" % template["name"])

                param_value = parameters[template["name"]]

            temp_len = template["length"] if "length" in template else 1
            temp_endian = template["byteorder"] if "byteorder" in template else "big"

            if temp_type == "bool":
                if param_value:
                    if "true-value" in template:
                        param_value = int(template["true-value"], 16)
                else:
                    if "false-value" in template:
                        param_value = int(template["false-value"], 16)

                data.extend(param_value.to_bytes(temp_len, temp_endian))
            elif temp_type == "int":
                temp_signed = template["signed"] if "signed" in template else False

                data.extend(
                    param_value.to_bytes(temp_len, temp_endian, signed=temp_signed)
                )
            elif temp_type == "str":
                param_bytes = param_value.encode("ascii")

                if temp_endian == "little":
                    param_bytes = param_bytes[::-1]

                data.extend(param_bytes)
            elif temp_type == "hex":
                data.extend(int(param_value, 16).to_bytes(temp_len, temp_endian))
            elif temp_type == "object":
                data.extend(
                    SR920Command._pack_parameters(param_value, template["properties"])
                )
            elif temp_type == "array":
                for item in param_value:
                    data.extend(
                        SR920Command._pack_parameters(
                            {template["items"]["name"]: item}, [template["items"]]
                        )
                    )
            elif temp_type.startswith("enum:"):
                data.extend(param_value.value.to_bytes(temp_len, temp_endian))
            else:  # bytes
                data.extend(param_value)

        return data

    @classmethod
    def _unpack_parameters(cls, parameters, data, templates):
        _logger.debug(
            "enter _unpack_parameters(): parameters=%s, data=%s, templates=%s",
            parameters,
            data,
            templates,
        )

        for template in templates:
            temp_type = template["type"]

            if temp_type.startswith("select:"):
                if temp_type[7:] not in parameters:
                    raise AttributeError(
                        "select variable not found: %s" % temp_type[7:]
                    )

                param_case = parameters[temp_type[7:]]

                # use name if select variable is an instance of Enum
                if isinstance(param_case, enum.Enum):
                    param_case = param_case.name

                default_case = None

                for temp_case in template["cases"]:
                    if "default" in temp_case:
                        default_case = temp_case["default"]
                    elif param_case in temp_case["case"]:
                        (parameters, data) = cls._unpack_parameters(
                            parameters, data, temp_case["parameters"]
                        )
                        default_case = None
                        break

                if default_case:
                    (parameters, data) = cls._unpack_parameters(
                        parameters, data, default_case
                    )

                continue

            if temp_type.startswith("ref:"):
                if temp_type[4:] not in _templates["definitions"]:
                    raise AttributeError("reference not found: %s" % temp_type[4:])

                reference = _templates["definitions"][temp_type[4:]]

                (parameters, data) = cls._unpack_parameters(parameters, data, reference)

                continue

            if "length" in template:
                param_bytes = data[: template["length"]]
                data = data[template["length"] :]
            else:
                param_bytes = data
                data = None

            if not param_bytes and temp_type not in ["array", "object"]:
                break

            if "value" in template:
                continue

            temp_name = template["name"]
            temp_endian = template["byteorder"] if "byteorder" in template else "big"

            # invert data if little endian
            if temp_endian == "little":
                param_bytes = param_bytes[::-1]

            if temp_type == "bool":
                if (
                    "true-value" in template
                    and param_bytes.hex() == template["true-value"]
                ):
                    param_bytes = b"\x01"
                elif (
                    "false-value" in template
                    and param_bytes.hex() == template["false-value"]
                ):
                    param_bytes = b"\x00"

                parameters[temp_name] = bool(int.from_bytes(param_bytes, "big"))
            elif temp_type == "int":
                temp_signed = template["signed"] if "signed" in template else False

                parameters[temp_name] = int.from_bytes(
                    param_bytes, "big", signed=temp_signed
                )
            elif temp_type == "str":
                parameters[temp_name] = param_bytes.decode("ascii")
            elif temp_type == "hex":
                parameters[temp_name] = param_bytes.hex()
            elif temp_type == "object":
                (parameters[temp_name], data) = cls._unpack_parameters(
                    {}, param_bytes, template["properties"]
                )
            elif temp_type == "array":
                parameters[temp_name] = []

                while param_bytes:
                    (params, param_bytes) = cls._unpack_parameters(
                        {}, param_bytes, [template["items"]]
                    )
                    parameters[temp_name].extend(params.values())
            elif temp_type.startswith("enum:"):
                enum_type = getattr(sr920.enums, temp_type[5:])
                parameters[temp_name] = enum_type(int.from_bytes(param_bytes, "big"))
            else:  # bytes
                parameters[temp_name] = param_bytes

        return parameters, data

    def __str__(self):
        # _logger.debug("enter __str__()")

        if self.parameters:
            return "SR920Command: command_id=%s, parameters=%s" % (
                self.command_id,
                self.parameters,
            )

        return "SR920Command: command_id=%s" % self.command_id
