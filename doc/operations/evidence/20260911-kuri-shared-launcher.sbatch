#!/bin/bash
# Site launcher probe. It does not inspect or process data.
#SBATCH --job-name=kamo-launcher-probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4000M
#SBATCH --time=00:03:00
#SBATCH --output=doc/operations/evidence/20260911-kuri-shared-launcher-%N-%j.txt

set -e
source /staff/Common/kuntaro/kamodev/activate-kamo.sh
cd /tmp

echo "job_id=${SLURM_JOB_ID:-unset}"
echo "hostname=$(hostname)"
echo "xds_par=$(command -v xds_par)"
echo "dials_version=$(command -v dials.version)"
echo "kamo=$(command -v kamo)"
dials.version
kamo --help >/dev/null
dials.python -B -c '
from yamtbx.command_line.kamo_test_installation import tst_xds
import sys
sys.exit(0 if tst_xds() else 1)
'
echo "shared_launcher_check=ok"
