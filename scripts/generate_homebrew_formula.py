#!/usr/bin/env python3
"""Generate a version-pinned third-party formula with offline wheel resources."""

import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def generate(revision, tag, resources, *, archive=None, sha256=None):
    if (not archive and not re.fullmatch(r"[0-9a-f]{40}", revision or "")) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("use an immutable source revision and semantic version tag")
    if archive and (not archive.startswith(("https://", "file://")) or not re.fullmatch(r"[0-9a-f]{64}", sha256 or "")):
        raise ValueError("archive sources require a file/HTTPS URL and SHA-256")
    source = ([f'  url "{archive}"', f'  sha256 "{sha256}"'] if archive else
              [f'  url "https://github.com/emaba/signing-tools.git", tag: "{tag}", revision: "{revision}"'])
    lines = [
        "# Third-party macOS tap: upstream wheels are pinned and SHA-256 verified.",
        "# This third-party distribution is not a homebrew/core submission.",
        "class SigningTools < Formula",
        '  desc "Local smart-card PDF and P7M signing with 1Password"',
        '  homepage "https://github.com/emaba/signing-tools"',
        *source,
        f'  version "{tag[1:]}"',
        "", '  depends_on "uv" => :build', '  depends_on "python@3.12"',
        '  depends_on "openssl@4"', '  depends_on "libp11"', '  depends_on "opensc"',
        '  depends_on macos: :ventura', "",
    ]
    if resources["architectures"] == ["arm64"]:
        lines += ["  depends_on arch: :arm64", ""]
    for arch, ruby in (("arm64", "on_arm"), ("x86_64", "on_intel")):
        if arch not in resources["architectures"]:
            continue
        lines += [f"  {ruby} do"]
        for resource in resources["resources"]:
            wheel = resource["wheels"][arch]
            lines += [f'    resource "{resource["name"].lower().replace("_", "-")}" do',
                      f'      url "{wheel["url"]}"',
                      f'      sha256 "{wheel["sha256"]}"', "    end", ""]
        lines += ["  end", ""]
    lines += '''  def install
    cache = buildpath/"uv-cache"
    wheelhouse = buildpath/"wheelhouse"
    wheelhouse.mkpath
    resources.each do |resource|
      wheelhouse.install resource.cached_download => File.basename(URI(resource.url).path)
    end
    uv = Formula["uv"].opt_bin/"uv"
    python = Formula["python@3.12"].opt_bin/"python3.12"
    system uv, "venv", "--no-config", "--no-project", "--no-python-downloads",
           "--cache-dir", cache, "--python", python, libexec
    system uv, "pip", "install", "--no-config", "--no-index", "--no-deps", "--link-mode", "copy",
           "--cache-dir", cache, "--python", libexec/"bin/python", *wheelhouse.children.map(&:to_s)
    system uv, "build", "--wheel", "--no-config", "--offline", "--no-build-isolation",
           "--cache-dir", cache, "--python", libexec/"bin/python", "--out-dir", buildpath/"dist", buildpath
    system uv, "pip", "install", "--no-config", "--no-index", "--no-deps", "--link-mode", "copy",
           "--cache-dir", cache, "--python", libexec/"bin/python", *Dir["#{buildpath}/dist/*.whl"]
    (libexec/"share/signing-tools").mkpath
    (libexec/"share/signing-tools/tools.json").write JSON.pretty_generate({
      openssl: (Formula["openssl@4"].opt_bin/"openssl").to_s,
      pkcs11_tool: (Formula["opensc"].opt_bin/"pkcs11-tool").to_s,
      provider_path: (Formula["libp11"].opt_lib/"ossl-modules").to_s,
    })
    bin.install_symlink libexec/"bin/signpdf", libexec/"bin/signp7m", libexec/"bin/signing-tools"
  end

  def caveats
    <<~EOS
      Install the issuer's PKCS#11 middleware and enable 1Password CLI integration.
      Existing shell-based setup: signing-tools migrate --plan; signing-tools migrate
      New setup: signing-tools configure
      Local prerequisite checks: signing-tools doctor
      Configuration is stored outside the Cellar and is preserved on upgrades/removal.
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/signing-tools --version")
    system bin/"signing-tools", "doctor", "--runtime-only"
    system bin/"signing-tools", "sample", testpath/"sample.pdf"
    assert_match "No signature fields found", shell_output("#{bin}/signpdf --list-fields #{testpath}/sample.pdf")
    assert_match version.to_s, shell_output("#{bin}/signp7m --version")
  end
end
'''.splitlines()
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision")
    parser.add_argument("--archive")
    parser.add_argument("--sha256")
    parser.add_argument("--tag", default="v0.1.2")
    parser.add_argument("--resources", type=Path, default=ROOT / "homebrew/resources.json")
    parser.add_argument("--output", type=Path, default=ROOT / "Formula/signing-tools.rb")
    args = parser.parse_args()
    output = generate(args.revision, args.tag, json.loads(args.resources.read_text()), archive=args.archive, sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output)
    print("Generated pinned Homebrew formula:", args.output)


if __name__ == "__main__":
    main()
