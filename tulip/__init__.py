"""Tulip 2.0, tracking PEP 3156."""

import sys

# This relies on each of the submodules having an __all__ variable.
from .futures import *
from .events import *
from .locks import *
from .transports import *
from .protocols import *
from .streams import *
from .tasks import *

if sys.platform == 'win32':  # pragma: no cover
    from .windows_events import *
else:
    from .unix_events import *


__all__ = (futures.__all__ +
           events.__all__ +
           locks.__all__ +
           transports.__all__ +
           protocols.__all__ +
           streams.__all__ +
           tasks.__all__)
