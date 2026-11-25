#!/usr/bin/env python3
"""Select checksummed upstream wheels for the private macOS Homebrew tap."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.request import urlopen

from packaging.tags import cpython_tags, compatible_tags, mac_platforms
from packaging.utils import parse_wheel_filename


ROOT = Path(__file__).resolve().parents[1]


def tags(arch):
    platforms = list(mac_platforms((13, 0), arch))
    ordered = list(cpython_tags((3, 12), platforms=platforms))
    ordered += list(compatible_tags((3, 12), interpreter="cp312", platforms=platforms))
    return {tag: index for index, tag in enumerate(ordered)}


def collect(requirement, architectures):
    name, version = requirement.split("==")
    with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        metadata = json.load(response)
    selected = {}
    for arch in architectures:
        supported = tags(arch)
        candidates = []
        for item in metadata["urls"]:
            if item["packagetype"] != "bdist_wheel" or item.get("yanked"):
                continue
            _, _, _, wheel_tags = parse_wheel_filename(item["filename"])
            ranks = [supported[tag] for tag in wheel_tags if tag in supported]
            if ranks and item["url"].startswith("https://files.pythonhosted.org/"):
                candidates.append((min(ranks), item["filename"], item))
        if not candidates:
            raise RuntimeError(f"No CPython 3.12 macOS wheel for {name}=={version} ({arch})")
        item = sorted(candidates, key=lambda candidate: candidate[:2])[0][2]
        selected[arch] = dict(filename=item["filename"], url=item["url"], sha256=item["digests"]["sha256"])
    return dict(name=name, version=version, wheels=selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "homebrew/resources.json")
    parser.add_argument("--architectures", nargs="+", choices=("arm64", "x86_64"), default=["arm64"])
    args = parser.parse_args()
    requirements = [line for line in (ROOT / "requirements-runtime.lock").read_text().splitlines()
                    if line and not line.startswith("#")]
    requirements.append("setuptools==84.2.1")
    with ThreadPoolExecutor(max_workers=4) as executor:
        resources = list(executor.map(lambda value: collect(value, args.architectures), requirements))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(python="3.12", macos_minimum="13.0", architectures=args.architectures, resources=resources),
                                      indent=2, sort_keys=True) + "\n")
    print("Recorded checksummed macOS wheels for", len(resources), "pinned packages:", ", ".join(args.architectures))


if __name__ == "__main__":
    main()
