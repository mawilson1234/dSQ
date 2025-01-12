#!/bin/env python
from __future__ import print_function
from datetime import datetime
from functools import partial
from os import path
from subprocess import Popen
import argparse
import os
import platform
import signal
import sys
import time

__version__ = 1.05


def forward_signal_to_child(pid, signum, frame):
    print("[dSQ]: ", pid, signum, frame)
    os.kill(pid, signum)


def exec_job(job_str):
    process = Popen(job_str, shell=True)
    signal.signal(signal.SIGCONT, partial(forward_signal_to_child, process.pid))
    signal.signal(signal.SIGTERM, partial(forward_signal_to_child, process.pid))
    return_code = process.wait()
    return return_code


desc = """Dead Simple Queue Batch v{}
https://github.com/ycrc/dSQ
A wrapper script to run job arrays from job files, where each line in the plain-text file is a self-contained job. This script is usually called from a batch script generated by dsq.

""".format(
    __version__
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=desc,
        usage="%(prog)s --job-file jobfile.txt [--suppress-stats-file | --status-dir dir/ ]",
        formatter_class=argparse.RawTextHelpFormatter,
        prog=path.basename(sys.argv[0]),
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s {}".format(__version__)
    )
    parser.add_argument(
        "--job-file",
        nargs=1,
        help="Job file, one job per line (not your job submission script).",
    )
    parser.add_argument(
        "--suppress-stats-file",
        action="store_true",
        help="Don't save job stats to stats file.",
    )
    parser.add_argument(
       "--status-dir",
       metavar="dir",
       nargs=1,
       default=".",
       help="Directory to save the stats file to. Defaults to working directory.",
    )
    parser.add_argument(
        "--stats-file",
        metavar="file",
        nargs=1,
        default="job_%j_status.tsv",
        help="Filename of the stats file. Defaults to job_jobid_status.tsv."
    )
    return parser.parse_args()


def run_job(args):
    jid = int(os.environ.get("SLURM_ARRAY_JOB_ID"))
    tid = int(os.environ.get("SLURM_ARRAY_TASK_ID"))
    # slurm calls individual job array indices "tasks"

    hostname = platform.node()
    
    if not args.stats_file[0].endswith(".tsv"):
        args.stats_file[0] += ".tsv"
    
    args.stats_file[0] = args.stats_file[0].replace("%j", str(jid))
    
    # use task_id to get my job out of job_file
    mycmd = ""
    with open(args.job_file[0], "r") as tf:
        for i, l in enumerate(tf):
            if i == tid:
                mycmd = l.strip()
                break

    # run job and track its execution time
    if mycmd == "":
        st = datetime.now()
        mycmd = "# could not find zero-indexed line {} in job file {}".format(
            tid, job_file
        )
        print(mycmd, file=sys.stderr)
        ret = 1
        et = datetime.now()
    else:
        st = datetime.now()
        ret = exec_job(mycmd)
        et = datetime.now()

    if not args.suppress_stats_file:
        # set up job stats
        out_cols = [
            "Array_Task_ID",
            "Exit_Code",
            "Hostname",
            "T_Start",
            "T_End",
            "T_Elapsed",
            "Task",
        ]
        time_fmt = "%Y-%m-%d %H:%M:%S"
        time_start = st.strftime(time_fmt)
        time_end = et.strftime(time_fmt)
        time_elapsed = (et - st).total_seconds()
        out_dict = dict(
            zip(
                out_cols,
                [tid, ret, hostname, time_start, time_end, time_elapsed, mycmd],
            )
        )
        
        # append status file with job stats
        with open(
            os.path.join(args.status_dir[0], args.stats_file[0]), "a"
            # os.path.join(args.status_dir[0], "job_{}_status.tsv".format(jid)), "a"
        ) as out_status:
            print(
                "{Array_Task_ID}\t{Exit_Code}\t{Hostname}\t{T_Start}\t{T_End}\t{T_Elapsed:.02f}\t{Task}".format(
                    **out_dict
                ),
                file=out_status,
            )

    sys.exit(ret)


if __name__ == "__main__":
    args = parse_args()
    run_job(args)
