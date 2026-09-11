#!/bin/sh
# Environment-only probe. It does not search for or process experimental data.
#SBATCH --job-name=kamo-path-probe
#SBATCH --partition=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:02:00
#SBATCH --output=doc/operations/evidence/20260911-kuri04-path-visibility-%j.txt

set -eu

echo "job_id=${SLURM_JOB_ID:-unset}"
echo "partition=${SLURM_JOB_PARTITION:-unset}"
echo "submit_host=${SLURM_SUBMIT_HOST:-unset}"
echo "node_list=${SLURM_JOB_NODELIST:-unset}"
echo "hostname=$(hostname)"
echo "pwd=$(pwd -P)"
uname -a
cat /etc/os-release

for probe_path in \
  /staff/Common/kuntaro/kamodev/kamo \
  /user/target
do
  if [ -e "$probe_path" ]; then
    echo "visible=$probe_path"
    stat -c 'mode=%A owner=%U group=%G path=%n' "$probe_path"
    findmnt -T "$probe_path" -o TARGET,SOURCE,FSTYPE,OPTIONS
  else
    echo "not_visible=$probe_path"
    exit 2
  fi
done

probe_file="doc/operations/evidence/.kuri04-path-write-${SLURM_JOB_ID}"
: > "$probe_file"
stat -c 'write_probe=ok mode=%A owner=%U group=%G path=%n' "$probe_file"
rm "$probe_file"
echo "write_probe_cleanup=ok"
