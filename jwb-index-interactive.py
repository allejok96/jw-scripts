#!/usr/bin/env python3
"""Helper script for running without terminal"""

import os
import shlex
import subprocess
import sys

script = 'jwb-index'
script_path = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), script)
subprocess.run([sys.executable, script_path, '--help'])
print('\nWorking directory:\n' + os.getcwd())

while True:
    args = input('\nType command (up/down for history, Ctrl+C to quit):\n> ' + script + ' ')
    subprocess.run([sys.executable, script_path] + shlex.split(args))