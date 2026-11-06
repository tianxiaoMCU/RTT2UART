"""Validate retained evidence and report its growth; never rewrite evidence."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


MANIFEST = "docs/evidence/issue13-artifacts.json"


def git(root: Path, *arguments: str, data: bytes | None = None,
        environment: dict[str, str] | None = None) -> bytes:
    return subprocess.run(["git", *arguments], cwd=root, input=data,
                          env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def evidence_files(root: Path) -> dict[str, bytes]:
    directory = root / "docs" / "evidence"
    if not directory.resolve().is_relative_to(root):
        raise ValueError("Evidence directory must remain inside the checkout")
    paths = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Evidence symlink is unsupported: {path}")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if "\n" in name or "\r" in name:
                raise ValueError(f"Evidence filenames cannot contain line breaks: {name!r}")
            paths.append(name)
    contents: dict[str, bytes] = {}
    if not paths:
        return contents
    # Isolate Git's clean conversion so validation never adds objects to this repository.
    with tempfile.TemporaryDirectory(prefix="rtt-evidence-objects-") as objects:
        environment = {**os.environ, "GIT_OBJECT_DIRECTORY": objects}
        original_objects = (root / os.fsdecode(git(root, "rev-parse", "--git-path", "objects")).strip()).resolve()
        alternates = environment.get("GIT_ALTERNATE_OBJECT_DIRECTORIES")
        environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(original_objects) + (os.pathsep + alternates if alternates else "")
        hashes = git(root, "hash-object", "-w", "--stdin-paths", environment=environment,
                     data="\n".join(paths).encode("utf-8") + b"\n")
        blobs = io.BytesIO(git(root, "cat-file", "--batch", data=hashes, environment=environment))
        for name in paths:
            header = blobs.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise ValueError(f"Git did not return canonical evidence bytes: {name}")
            contents[name] = blobs.read(int(header[2]))
            if blobs.read(1) != b"\n":
                raise ValueError(f"Truncated Git evidence blob: {name}")
    return contents


def validate_manifest(contents: dict[str, bytes]) -> None:
    document = json.loads(contents[MANIFEST])
    if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
            or document["schema_version"] != 1):
        raise ValueError("Unsupported evidence manifest schema")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Manifest artifacts must be a list")
    listed = set()
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Each manifest artifact needs a path")
        name = item["path"]
        path = PurePosixPath(name)
        if (not name.startswith("docs/evidence/") or name != path.as_posix()
                or ".." in path.parts or "\\" in name or ":" in name or "\0" in name):
            raise ValueError(f"Invalid evidence path: {name!r}")
        if name == MANIFEST or name in listed:
            raise ValueError(f"Duplicate or self-referential manifest path: {name}")
        listed.add(name)
        size, digest = item.get("bytes"), item.get("sha256")
        if type(size) is not int or size < 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid byte count or SHA256: {name}")
        if name not in contents:
            raise ValueError(f"Missing evidence file: {name}")
        if len(contents[name]) != size or hashlib.sha256(contents[name]).hexdigest() != digest:
            raise ValueError(f"Evidence byte count or SHA256 mismatch: {name}")
    unlisted = set(contents) - {MANIFEST} - listed
    if unlisted:
        raise ValueError(f"Unlisted evidence files: {', '.join(sorted(unlisted))}")


def validate_duplicates(contents: dict[str, bytes]) -> None:
    seen: dict[str, str] = {}
    for name, data in contents.items():
        if name == MANIFEST:
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            raise ValueError(f"Duplicate evidence content: {seen[digest]} and {name}")
        seen[digest] = name


def validate_links(root: Path, contents: dict[str, bytes]) -> None:
    tracked = {os.fsdecode(p) for p in git(root, "ls-files", "-z").split(b"\0") if p}
    documents = {name for name in tracked | set(contents) if name.endswith(".md")}
    # shortcut: validate destination files, not heading fragments or remote URLs.
    target = r'(?:<([^>\n]+)>|((?:\\.|[^\s()\\]|\([^()\n]*\))+))'
    inline = re.compile(r'\]\(\s*' + target + r'''(?:\s+"[^"]*"|\s+'[^']*'|\s+\([^)]*\))?\s*\)''')
    reference = re.compile(r'^ {0,3}\[([^\]]+)\]:[ \t]*' + target, re.MULTILINE)
    count = 0
    for name in sorted(documents):
        source = root / name
        if not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError(f"Missing Markdown document: {name}")
        lines = []
        fence = ""
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
            if marker:
                token = marker[1]
                if not fence:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = ""
            elif not fence:
                lines.append(line)
        text = re.sub(r'(`+).*?\1', '', '\n'.join(lines), flags=re.DOTALL)
        definitions = {" ".join(m[1].lower().split()): m[2] or m[3] for m in reference.finditer(text)}
        destinations = [m[1] or m[2] for m in inline.finditer(text)] + list(definitions.values())
        for destination in destinations:
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            local = re.sub(r'\\([\\() ])', r'\1', unquote(parsed.path))
            path = root / local.lstrip("/") if local.startswith("/") else source.parent / local
            if not path.resolve().is_relative_to(root) or not path.exists():
                raise ValueError(f"Broken local Markdown link in {name}: {destination}")
            count += 1
    print(f"Local Markdown destinations checked: {count}")


def report_growth(root: Path, contents: dict[str, bytes], base: str) -> None:
    previous = {}
    if base not in ("0" * 40, "0" * 64):
        tree = git(root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{tree}}").decode().strip()
        for row in git(root, "ls-tree", "-rlz", tree, "--", "docs/evidence").split(b"\0"):
            if row:
                metadata, encoded_name = row.split(b"\t", 1)
                previous[os.fsdecode(encoded_name)] = int(metadata.split()[3])
    added = set(contents) - set(previous)
    removed = set(previous) - set(contents)
    total = sum(len(data) for data in contents.values())
    print(f"Evidence baseline: {base}")
    print(f"Evidence total: {len(contents)} files ({total} bytes)")
    print(f"Added evidence files: {len(added)} ({sum(len(contents[p]) for p in added)} bytes)")
    print(f"Removed evidence files: {len(removed)} ({sum(previous[p] for p in removed)} bytes)")
    print(f"Evidence byte change: {total - sum(previous.values()):+d}")
    for name in sorted(added):
        print(f"  + {name} ({len(contents[name])} bytes)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("EVIDENCE_BASE") or "HEAD",
                        help="Growth baseline; defaults to EVIDENCE_BASE or HEAD")
    args = parser.parse_args(argv)
    try:
        root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip()).resolve()
        contents = evidence_files(root)
        report_growth(root, contents, args.base)
        validate_manifest(contents)
        validate_duplicates(contents)
        validate_links(root, contents)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Evidence check failed: {error}", file=sys.stderr)
        return 1
    print("Evidence checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
