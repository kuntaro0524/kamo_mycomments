#!/bin/sh
# Environment-only probe. It does not search for or process experimental data.
# Submit with an explicit partition and node.
#SBATCH --job-name=kamo-node-survey
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:02:00
#SBATCH --output=doc/operations/evidence/20260911-kuri-node-survey-%N-%j.txt

set -eu

echo "job_id=${SLURM_JOB_ID:-unset}"
echo "partition=${SLURM_JOB_PARTITION:-unset}"
echo "submit_host=${SLURM_SUBMIT_HOST:-unset}"
echo "node_list=${SLURM_JOB_NODELIST:-unset}"
echo "hostname=$(hostname)"
echo "pwd=$(pwd -P)"
echo "tmpdir=${TMPDIR:-unset}"
uname -a
cat /etc/os-release
lscpu

for probe_path in \
  /staff/Common/kuntaro/kamodev/kamo \
  /user/target \
  /tmp
do
  if [ -e "$probe_path" ]; then
    echo "visible=$probe_path"
    stat -c 'mode=%A owner=%U group=%G path=%n' "$probe_path"
    df -T "$probe_path"
    findmnt -T "$probe_path" -o TARGET,SOURCE,FSTYPE,OPTIONS
  else
    echo "not_visible=$probe_path"
    exit 2
  fi
done

shared_probe="doc/operations/evidence/.kuri-node-shared-write-${SLURM_JOB_ID}"
: > "$shared_probe"
stat -c 'shared_write_probe=ok mode=%A owner=%U group=%G path=%n' "$shared_probe"
rm "$shared_probe"
echo "shared_write_probe_cleanup=ok"

local_probe="/tmp/kamo-node-local-write-${SLURM_JOB_ID}"
: > "$local_probe"
stat -c 'local_write_probe=ok mode=%A owner=%U group=%G path=%n' "$local_probe"
rm "$local_probe"
echo "local_write_probe_cleanup=ok"
