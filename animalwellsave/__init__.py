
# Software version
__version__ = '1.1.0'

# Debug (basically just outputting offsets for our vars)
_debug = False

def is_debug():
    global _debug
    return _debug

def set_debug():
    global _debug
    _debug = True
