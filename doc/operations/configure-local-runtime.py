#!/usr/bin/env python3
"""Configure a private copy of a DIALS binary installation for this checkout.

First copy DIALS to a NEW writable directory with cp -a. Never pass the shared
installation as --runtime. The script intentionally does not copy the runtime.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--checkout', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    checkout = args.checkout.resolve()
    if not (runtime / 'conda_base/bin/python').is_file():
        parser.error('Expected a copied DIALS installation with conda_base/bin/python')
    if not (checkout / 'yamtbx/libtbx_config').is_file():
        parser.error('Expected a yamtbx checkout')
    module = runtime / 'modules/yamtbx'
    backup = runtime / 'original-yamtbx'
    if module.is_symlink():
        if module.resolve() != checkout:
            parser.error('Existing yamtbx symlink points at a different checkout')
    elif module.exists():
        if backup.exists():
            parser.error('Backup already exists; inspect runtime before proceeding')
        module.rename(backup)
        module.symlink_to(checkout, target_is_directory=True)
    else:
        module.symlink_to(checkout, target_is_directory=True)

    # DIALS binary distributions can retain their original installation prefix
    # in this dispatcher include. Keep all other dispatcher settings unchanged.
    include = runtime / 'build/dispatcher_include_dials.sh'
    lines = include.read_text().splitlines(keepends=True)
    replacement = 'export DIALS=' + shlex.quote(str(runtime)) + '\n'
    if not any(line.startswith('export DIALS=') for line in lines):
        parser.error('No DIALS prefix setting found in dispatcher include')
    include.write_text(''.join(replacement if line.startswith('export DIALS=')
                               else line for line in lines))

    cache = runtime / 'runtime-cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['MPLCONFIGDIR'] = str(cache)
    subprocess.run([str(runtime / 'build/bin/libtbx.configure'), 'yamtbx'],
                   cwd=runtime / 'build', env=env, check=True)

    # Bash activation is machine-local generated configuration, not repo code.
    activation = ('# Generated Bash activation for this private runtime.\n'
                  + replacement
                  + 'export MPLCONFIGDIR=' + shlex.quote(str(cache)) + '\n'
                  + 'source ' + shlex.quote(str(runtime / 'build/setpaths.sh')) + '\n')
    (runtime / 'activate.sh').write_text(activation)
    (runtime / 'dials_env.sh').write_text(activation)
    print('Activate in Bash: source ' + shlex.quote(str(runtime / 'activate.sh')))


if __name__ == '__main__':
    main()
