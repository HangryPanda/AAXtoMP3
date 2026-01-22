import sys
import os
sys.path.append(os.path.join(os.getcwd(), "apps", "api"))

try:
    import services.audible_client as ac
    print("Module file:", ac.__file__)
    print("Contents:", dir(ac))
except Exception as e:
    print(e)
