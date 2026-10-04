# -*- coding: utf-8 -*-
"""python -m moteur_v2_6_10 --autotest  : autotests du moteur v2.6.10 (remplace `python moteur_v2_6_9.py --autotest`)."""
import sys

from .autotest import autotest

if __name__ == "__main__":
    if "--autotest" in sys.argv[1:]:
        sys.exit(autotest())
    print("Usage : python -m moteur_v2_6_10 --autotest")
    sys.exit(2)
