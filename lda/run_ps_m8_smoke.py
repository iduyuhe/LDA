import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.ps_m8 import main

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m8")
    raise SystemExit(main(out_dir=_out))
