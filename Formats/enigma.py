from Formats.decompress import Decompress
from Formats.compress import Compress

class EnigmaDecomp(Decompress):
    """
    Decompress a Enigma-encoded file.
    """
    def decompress(self):
        pass

class EnigmaComp(Compress):
    """
    Compress a file in the Enigma format.
    """
    def compress(self):
        pass

# ========================
# Callers
# ========================
# This defines what gets imported if using 'from Editors import *'
__all__ = ["compress", "decompress"]

def compress(data, xor_mode=None):
    comp = EnigmaComp(data)
    #return comp.compress()

def decompress(data):
    decomp = EnigmaDecomp(data)
    #return decomp.decompress()
