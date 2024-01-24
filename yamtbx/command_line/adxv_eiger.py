# LIBTBX_SET_DISPATCHER_NAME yamtbx.adxv_eiger
# LIBTBX_PRE_DISPATCHER_INCLUDE_SH export PHENIX_GUI_ENVIRONMENT=1
"""
(c) RIKEN 2016. All rights reserved. 
Author: Keitaro Yamashita

This software is released under the new BSD License; see LICENSE.
"""

import dxtbx.format # to set HDF5_PLUGIN_PATH in phenix environment
try: # now dxtbx.format does not work
    import hdf5plugin
except ImportError:
    pass
from yamtbx.dataproc.command_line import adxv_eiger

if __name__ == "__main__":
    import sys
    adxv_eiger.run(sys.argv[1:])
