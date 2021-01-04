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

## Quick Start

```python
>>> # import sr920 package
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
