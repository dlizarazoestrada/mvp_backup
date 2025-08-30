# run_backend.py
import os
import sys
import runpy

# This script is the new entry point for the PyInstaller-built executable.
# Its purpose is to set up the Python path correctly so that all absolute imports
# within the 'backend' package work as expected.

if __name__ == '__main__':
    # When PyInstaller creates the bundle, it places all our files in a directory
    # that it specifies in sys._MEIPASS. This is our new "root" directory.
    # We add this root to the path to make 'backend' a discoverable package.
    if hasattr(sys, '_MEIPASS'):
        os.chdir(sys._MEIPASS)
        sys.path.insert(0, sys._MEIPASS)

    # Instead of importing, we use runpy.run_module to execute 'backend.main'.
    # This executes the module as if we had run `python -m backend.main`,
    # which is the correct way to run a script inside a package.
    # It ensures that relative imports within the package also work correctly.
    runpy.run_module('backend.main', run_name='__main__')
