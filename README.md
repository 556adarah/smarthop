# smarthop

_smarthop_ is an **unofficial** python package for handling [OKI SmartHop wireless modules](https://www.oki.com/jp/920M/).

## Install

You can install _smarthop_ using by pip from GitHub.

```bash
$ pip install git+https://github.com/556adarah/smarthop
```

## Requirements

- Python 3.6 or higher
- [pyserial](https://pythonhosted.org/pyserial/) 3.0 or higher
- [jsonschema](https://python-jsonschema.readthedocs.io/en/stable/)
- [tqdm](https://tqdm.github.io/)

## Quick Start

```python
>>> # import smarthop.sr920 package
>>> from smarthop import sr920

>>> # create an instance with the specified serial port
>>> sr = sr920.SR920("/dev/ttyS4")

>>> # load configurations from JSON document
>>> sr.load_config("coordinator.json")
True

>>> # start operation
>>> sr.start()
True

>>> # send data to the destination 0002
>>> sr.send_data(b"Hello, world!", destination="0002")
True

>>> # close serial port
>>> sr.close()

>>> # or you can use the 'with' statement
>>> with sr920.SR920("/dev/ttyS4") as sr:
...   sr.load_config("coordinator.json")
...   sr.start()
...   sr.send_data(b"Hello, world!", destination="0002")
...
True
True
True
```

Please see [references](https://github.com/556adarah/smarthop/wiki/References) for details.
Note that references are provided only in Japanese.

## History

### v0.1 beta 3

- NEW: SR920 supports to load configurations from CSV file.
- NEW: SR920 supports to extract configurations from the SR module.
- NEW: JSON configuration supports all configurations for the SR module.
- FIX: wrong encoding for TIME_SYNC configuration

### v0.1 beta 2

- NEW: SR920 supports radio status measurement, firmware update and channel scan features.
- NEW: SR920.mac_address property.
- NEW: 4 shortcut and 1 new methods for controling fixed address list.
- NEW: tqdm package required.
- CHANGE: rename parameter on NETWORK_STATE_CHANGED_NOTIFICATION and SR920.get_network_address(); coordinator_address -> coordinator
- CHANGE: refine command timeout.
- FIX: wrong value of SR920CommandId.
- FIX: misspelled argument on SR920.measure_rtt().

### v0.1 beta 1

- Initial beta release for smarthop package.
