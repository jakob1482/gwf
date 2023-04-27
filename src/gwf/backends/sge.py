"""Backend for Sun Grid Engine (SGE).

To use this backend you must activate the `sge` backend. The backend
currently assumes that a SGE parallel environment called "smp" is
available. You can check which parallel environments are available on your
system by running :command:`qconf -spl`.

**Backend options:**

None.

**Target options:**

* **cores (int):**
    Number of cores allocated to this target (default: 1).
* **memory (str):**
    Memory allocated to this target (default: 1).
* **walltime (str):**
    Time limit for this target (default: 01:00:00).
* **queue (str):**
    Queue to submit the target to. To specify multiple queues, specify a
    comma-separated list of queue names.
* **account (str):**
    Account to be used when running the target. Corresponds to the SGE
    project.
"""

import logging
import os.path
import re
from xml.etree import ElementTree

import attrs

from ..utils import ensure_trailing_newline
from .base import BackendStatus, TrackingBackend
from .utils import call, has_exe

logger = logging.getLogger(__name__)


TARGET_DEFAULTS = {
    "cores": 1,
    "memory": "1g",
    "walltime": "01:00:00",
    "queue": None,
    "account": None,
}

OPTION_FLAGS = {
    "cores": "-pe smp ",
    "memory": "-l h_vmem=",
    "walltime": "-l h_rt=",
    "queue": "-q ",
    "account": "-P ",
}


@attrs.define
class SGEOps:
    working_dir: str = attrs.field()
    target_defaults: dict = attrs.field()

    def cancel_job(self, job_id):
        # The --verbose flag here is necessary, otherwise we're not able to tell
        # whether the command failed. See the comment in call() if you
        # want to know more.
        return call("qdel", job_id)

    def submit_target(self, target, dependencies):
        script = self.compile_script(target)
        args = ["-terse"]
        if dependencies:
            args.append("-hold_jid")
            args.append(",".join(dependencies))
        return call("qsub", *args, input=script)

    def get_job_states(self, tracked_jobs):
        job_states = {}
        root = ElementTree.fromstring(call("qstat", "-f", "-xml"))
        for job in root.iter("job_list"):
            job_id = job.find("JB_job_number").text
            state = job.find("state").text
            assert job_id is not None
            assert state is not None

            # Guessing job state based on
            # https://gist.github.com/cmaureir/4fa2d34bc9a1bd194af1
            if "d" in state or "E" in state:
                job_state = BackendStatus.UNKNOWN
            elif "r" in state or "t" in state or "s" in state:
                job_state = BackendStatus.RUNNING
            else:
                job_state = BackendStatus.SUBMITTED
            job_states[job_id] = job_state
        return job_states

    def compile_script(self, target):
        option_str = "#$ {0}{1}"

        out = []
        out.append("#!/bin/bash")
        out.append("# Generated by: gwf")

        out.append(option_str.format("-N ", target.name))
        out.append("#$ -V")
        out.append("#$ -w v")
        out.append("#$ -cwd")

        for option_name, option_value in target.options.items():
            # SGE wants per-core memory, but gwf wants total memory.
            if option_name == "memory":
                number = int(re.sub(r"[^0-9]+", "", option_value))
                unit = re.sub(r"[0-9]+", "", option_value)
                cores = target.options["cores"]
                option_value = "{}{}".format(number // cores, unit)
            out.append(option_str.format(OPTION_FLAGS[option_name], option_value))

        out.append(
            option_str.format(
                "-o ",
                os.path.join(self.working_dir, ".gwf", "logs", target.name + ".stdout"),
            )
        )
        out.append(
            option_str.format(
                "-e ",
                os.path.join(self.working_dir, ".gwf", "logs", target.name + ".stderr"),
            )
        )

        out.append("")
        out.append("cd {}".format(target.working_dir))
        out.append("export GWF_JOBID=$SGE_JOBID")
        out.append('export GWF_TARGET_NAME="{}"'.format(target.name))
        out.append("set -e")
        out.append("")
        out.append(ensure_trailing_newline(target.spec))
        return "\n".join(out)


def create_backend(working_dir):
    return TrackingBackend(
        working_dir,
        name="sge",
        ops=SGEOps(working_dir, target_defaults=TARGET_DEFAULTS),
    )


def priority():
    if has_exe("qsub") and has_exe("qdel"):
        return 50
    return -100


setup = (create_backend, priority())
