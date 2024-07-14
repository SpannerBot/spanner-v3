#!/bin/env python3
import datetime
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger("spanner.version")


def should_write() -> bool:
    """Checks whether the version file should be written."""
    # 1. Check if the environment variable is set. If it is, and it's not a vaguely false value, should write.
    if os.getenv("SPANNER_WRITE_VERSION", "0") not in ["0", "false", "no", ""]:
        return True

    # 2. Check if it already exists *and is automatically created*.
    # The stub file is created for the purposes of assisting IDEs, and should be overwritten
    root = find_project_dir()
    if (root / "share" / "version.py").exists():
        try:
            from share.version import __auto__
        except ImportError:
            __auto__ = False
    else:
        __auto__ = False

    # If the file did not exist, or was not automatically generated, should write.
    return not __auto__


def find_project_dir(start: Path = None, subdir: str = "share") -> Path:
    """Helper function to find where `spanner.share` actually is.

    re-purposed to find .git too"""
    _FNF = FileNotFoundError("Could not find project directory.")
    start = start or Path.cwd()
    if (start / subdir).is_dir():
        logger.info("Found project directory at %s.", start)
        return start
    logger.info("Searching for project directory (%s) in %s, as %s did not have it.", subdir, start.parent, start)

    if start.parent == start:
        raise _FNF
    try:
        return find_project_dir(start.parent, subdir)
    except RecursionError:
        raise _FNF from None


def gather_version_info() -> tuple[str, str, datetime.datetime]:
    build_time = datetime.datetime.fromtimestamp(Path(__file__).stat().st_mtime, tz=datetime.timezone.utc)
    try:
        find_project_dir(subdir=".git")
    except FileNotFoundError:
        logger.warning(
            "Git repository was not found, fetching version info from remote and environment.", exc_info=True
        )
        try:
            response = httpx.get(
                "https://git.i-am.nexus/api/v1/repos/nex/spanner-v3/commits",
                params={
                    "path": "spanner/main.py",
                    "stat": "false",
                    "verification": "false",
                    "files": "false",
                    "sha": "dev",
                },
            )
            response.raise_for_status()
            commits = response.json()
            for commit in commits:
                ctime = datetime.datetime.fromisoformat(commit["created"])
                if ctime == build_time:
                    break
            else:
                commit = commits[0]
            sha = commit["sha"]
            sha_short = sha[:7]
            c_build_time = datetime.datetime.fromisoformat(commit["created"])
            build_time = min(build_time, c_build_time)  # pick the oldest one here.
        except (httpx.HTTPError, ConnectionError) as e:
            logger.warning("Failed to get latest commit from git.i-am.nexus: %s", e)
            sha = sha_short = "unknown"
    else:
        # Both a development environment, and the docker environment, include .git.
        # The docker environment contains a treeless clone though, so we should only rely on the latest commit.
        logger.info("Generating first-run version info with git.")
        sha = subprocess.getoutput("git rev-parse HEAD") or os.urandom(20).hex()
        sha_short = sha[:7]
        build_time_ts = subprocess.getoutput("git show -s --format=%ct HEAD")
        try:
            build_time_ts = int(build_time_ts)
        except ValueError:
            logger.warning("Failed to get build time from git - expected integer, got %r.", build_time_ts)
            build_time_ts = round(time.time())
        build_time = datetime.datetime.fromtimestamp(build_time_ts, tz=datetime.timezone.utc)

    return sha, sha_short, build_time


def write_version_file(sha: str, sha_short: str, build_time: datetime.datetime) -> None:
    """
    Writes the python file, ready for importing.
    """
    with open(find_project_dir() / "share" / "version.py", "w") as f:
        lines = [
            "import datetime",
            "__auto__ = True",
            f'__sha__ = "{sha}"',
            f'__sha_short__ = "{sha_short}"',
            f"__build_time__ = {build_time!r}",
            '__all__=("__auto__", "__sha__", "__sha_short__", "__build_time__")',
            "del datetime",
        ]
        f.write("\n".join(lines))


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s: %(name)s: %(levelname)s: %(message)s")
    logger.setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser(description="Generate version information for spanner.")
    parser.add_argument("-f", "--force", action="store_true", help="Forcefully write the version file.")
    parser.add_argument("-s", "--show", action="store_true", help="Show the version information and exit.")
    args = parser.parse_args()
    logger.info("writing version info (manually invoked)")
    if not should_write():
        logger.warning("A version re-write was not necessary.")
        if args.force is not True:
            logger.warning("Use --force to override.")
            sys.exit(0)
    write_version_file(*gather_version_info())
    logger.info("Testing that the version file was written correctly.")
    try:
        from share.version import *
    except ImportError as e:
        logger.error("Failed to import version file!", exc_info=e)
    else:
        logger.info("Version info written successfully.")

    if args.show:
        from share.version import __build_time__, __sha__, __sha_short__

        print("Version information:")
        print(f"Full SHA: {__sha__}")
        print(f"Short SHA: {__sha_short__}")
        print(f"Build time: {__build_time__}")
