from __future__ import unicode_literals

import time
from math import pi, cos, sin

TEMPLATE = """# File Automaticaly generated by XIO
#       date: %s
#       Beamline SOLEIL-Proxima1
#       Detector type: ADSC 315r
""" % (time.ctime())

TEMPLATE += """

#  Basic definitions
 gain 1.15
 adcoff 39
 synchrotron polar 0.99
 dispersion  0.0004
 divergence  0.09 0.009

 genf genfile.gen

#  Better have them
WAVELENGTH  %(WAVELENGTH).5f

! resolution 2
! BEAM  %(BEAMX).2f  %(BEAMY).2f
DISTANCE  %(DISTANCE).2f
DISTORTION YSCALE    0.9999 TILT    0 TWIST  -28


#  Just a guess
 mosaic  0.35

#  Files
# directory       ../../
 template  %(NAME_TEMPLATE)s
# extention  img
 image  %(STARTING_NUMBER)d
 phi    %(STARTING_ANGLE).2f to %(ENDING_ANGLE).2f

 go
"""


HTD = {
'WAVELENGTH':(['Wavelength'], float),
'DISTANCE':(['Distance'], float),
'STARTING_ANGLE':(['PhiStart'], float),
'ENDING_ANGLE':(['PhiStart', 'PhiWidth'], lambda x,y: x+y),
'OSCILLATION_RANGE':(['PhiWidth'], float),
'NX':(['Width'], int),
'NY':(['Height'], int),
'QX':(['PixelX'], float),
'QY':(['PixelY'], float),
'BEAMX':(['BeamX'], float), # Yes, it is in revers order.
'BEAMY':(['BeamY'], float), # DoNotAsk!
}
        
#     Collect Translator Dictionary.
#     Translate collect object attributes to a new dictionay
#     newdic['SPOT_RANGE'] = list(collect.imageRanges)
#
CTD = {
'NAME_TEMPLATE':(['mosflmTemplate'], str),
'STARTING_NUMBER':(['imageNumbers'], lambda x: x[0]),
'DETECTOR':(['imageType'], lambda x: x.upper()),
}
