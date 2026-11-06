"""Check Git whitespace errors in local and CI changes without editing files."""
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    base = os.environ.get("EVIDENCE_BASE") or "HEAD"
    print(f"Whitespace baseline: {base}", flush=True)
    try:
        arguments = (["hash-object", "-t", "tree", "--stdin"]
                     if base in ("0" * 40, "0" * 64) else
                     ["rev-parse", "--verify", "--end-of-options", f"{base}^{{tree}}"])
        tree = subprocess.check_output(["git", *arguments], cwd=root, input=b"").decode("ascii").strip()
        # Check the index separately: clean working bytes can mask a staged error.
        for options in ((tree,), ("--cached", tree)):
            result = subprocess.run(["git", "diff", "--check", *options, "--"], cwd=root)
            if result.returncode:
                return result.returncode
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Whitespace check failed: {error}", file=sys.stderr)
        return 1
    print("Whitespace checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
