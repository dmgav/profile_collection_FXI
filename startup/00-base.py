import nslsii
from datetime import datetime

# Register bluesky IPython magics.
from bluesky.magics import BlueskyMagics

get_ipython().register_magics(BlueskyMagics)

from bluesky.preprocessors import stage_decorator, run_decorator
from databroker.v0 import Broker
db = Broker.named('fxi')
del Broker

nslsii.configure_base(get_ipython().user_ns, db, bec=True)


# Make new RE.md storage available in old environments.
from pathlib import Path

import appdirs


try:
    from bluesky.utils import PersistentDict
except ImportError:
    import msgpack
    import msgpack_numpy
    import zict

    class PersistentDict(zict.Func):
        def __init__(self, directory):
            self._directory = directory
            self._file = zict.File(directory)
            super().__init__(self._dump, self._load, self._file)

        @property
        def directory(self):
            return self._directory

        def __repr__(self):
            return f"<{self.__class__.__name__} {dict(self)!r}>"

        @staticmethod
        def _dump(obj):
            "Encode as msgpack using numpy-aware encoder."
            # See https://github.com/msgpack/msgpack-python#string-and-binary-type
            # for more on use_bin_type.
            return msgpack.packb(
                obj,
                default=msgpack_numpy.encode,
                use_bin_type=True)

        @staticmethod
        def _load(file):
            return msgpack.unpackb(
                file,
                object_hook=msgpack_numpy.decode,
                raw=False)

runengine_metadata_dir = appdirs.user_data_dir(appname="bluesky") / Path("runengine-metadata")

# PersistentDict will create the directory if it does not exist
RE.md = PersistentDict(runengine_metadata_dir)

# disable plotting from best effort callback
bec.disable_plots()

from databroker.assets.handlers import AreaDetectorHDF5TimestampHandler
import pandas as pd


EPICS_EPOCH = datetime(1990, 1, 1, 0, 0)


def convert_AD_timestamps(ts):
    return pd.to_datetime(ts, unit="s", origin=EPICS_EPOCH, utc=True).dt.tz_convert(
        "US/Eastern"
    )


# subscribe the zmq plotter

from bluesky.callbacks.zmq import Publisher

publisher = Publisher("xf18id-srv1:5577")
RE.subscribe(publisher)

# nslsii.configure_base(get_ipython().user_ns, 'fxi', bec=False)

"""
def ts_msg_hook(msg):
    t = '{:%H:%M:%S.%f}'.format(datetime.now())
    msg_fmt = '{: <17s} -> {!s: <15s} args: {}, kwargs: {}'.format(
        msg.command,
        msg.obj.name if hasattr(msg.obj, 'name') else msg.obj,
        msg.args,
        msg.kwargs)
    print('{} {}'.format(t, msg_fmt))

RE.msg_hook = ts_msg_hook
"""


## HACK HACK

def rd(obj, *, default_value=0):
    """Reads a single-value non-triggered object

    This is a helper plan to get the scalar value out of a Device
    (such as an EpicsMotor or a single EpicsSignal).

    For devices that have more than one read key the following rules are used:

    - if exactly 1 field is hinted that value is used
    - if no fields are hinted and there is exactly 1 value in the
      reading that value is used
    - if more than one field is hinted an Exception is raised
    - if no fields are hinted and there is more than one key in the reading an
      Exception is raised

    The devices is not triggered and this plan does not create any Events

    Parameters
    ----------
    obj : Device
        The device to be read
    default_value : Any
        The value to return when not running in a "live" RunEngine.
        This come ups when ::

           ret = yield Msg('read', obj)
           assert ret is None

        the plan is passed to `list` or some other iterator that
        repeatedly sends `None` into the plan to advance the
        generator.

    Returns
    -------
    val : Any or None
        The "single" value of the device

    """
    hints = getattr(obj, 'hints', {}).get("fields", [])
    if len(hints) > 1:
        msg = (
            f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
            f"has {len(hints)} items hinted ({hints}).  We do not know how to "
            "pick out a single value.  Please adjust the hinting by setting the "
            "kind of the components of this device or by rd ing one of it's components"
        )
        raise ValueError(msg)
    elif len(hints) == 0:
        hint = None
        if hasattr(obj, "read_attrs"):
            if len(obj.read_attrs) != 1:
                msg = (
                    f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
                    f"and has {len(obj.read_attrs)} read attrs.  We do not know how to "
                    "pick out a single value.  Please adjust the hinting/read_attrs by "
                    "setting the kind of the components of this device or by rd ing one "
                    "of its components"
                )

                raise ValueError(msg)
    # len(hints) == 1
    else:
        (hint,) = hints

    ret = yield from read(obj)

    # list-ify mode
    if ret is None:
        return default_value

    if hint is not None:
        return ret[hint]["value"]

    # handle the no hint 1 field case
    try:
        (data,) = ret.values()
    except ValueError as er:
        msg = (
            f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
            f"and has {len(ret)} read values.  We do not know how to pick out a "
            "single value.  Please adjust the hinting/read_attrs by setting the "
            "kind of the components of this device or by rd ing one of its components"
        )

        raise ValueError(msg) from er
    else:
        return data["value"]

# monkey batch bluesky.plans_stubs to fix bug.
bps.rd = rd
