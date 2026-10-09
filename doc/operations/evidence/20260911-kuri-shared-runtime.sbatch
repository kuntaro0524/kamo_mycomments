#!/bin/bash
# Shared DIALS/KAMO runtime probe. It does not inspect or process data.
#SBATCH --job-name=kamo-runtime-probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4000M
#SBATCH --time=00:03:00
#SBATCH --output=doc/operations/evidence/20260911-kuri-shared-runtime-%N-%j.txt

set -e

runtime=/staff/Common/kuntaro/kamodev/runtimes/dials-3.23.0-kamo-c811f9f21a177bc97e9f21066d3585474aa880a1
checkout=/staff/Common/kuntaro/kamodev/checkouts/kamo-c811f9f21a177bc97e9f21066d3585474aa880a1

echo "job_id=${SLURM_JOB_ID:-unset}"
echo "partition=${SLURM_JOB_PARTITION:-unset}"
echo "hostname=$(hostname)"
uname -a

test -r "$runtime/activate.sh"
test -r "$checkout/yamtbx/__init__.py"
. "$runtime/activate.sh"
set -u
cd /tmp

echo "dials_version_command=$(command -v dials.version)"
echo "kamo_command=$(command -v kamo)"
echo "dials_python_command=$(command -v dials.python)"
dials.version
kamo --help >/dev/null
echo "kamo_help=ok"

dials.python -B -c '
import os
import sys
import yamtbx
from yamtbx import util
print("python=" + sys.executable)
print("yamtbx=" + os.path.realpath(yamtbx.__file__))
print("resources=" + os.path.realpath(util.yamtbx_module_root()))
print("cwd=" + os.getcwd())
'

test "$(git -C "$checkout" rev-parse HEAD)" = c811f9f21a177bc97e9f21066d3585474aa880a1
test -z "$(git -C "$checkout" status --short)"
echo "checkout_commit_and_state=ok"
