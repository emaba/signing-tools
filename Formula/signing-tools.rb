# Third-party macOS tap: upstream wheels are pinned and SHA-256 verified.
# This third-party distribution is not a homebrew/core submission.
class SigningTools < Formula
  desc "Local smart-card PDF and P7M signing with 1Password"
  homepage "https://github.com/emaba/signing-tools"
  url "https://github.com/emaba/signing-tools.git", tag: "v0.1.2", revision: "a3440bac99e920c2505ff812f3e8b12d5035774d"
  version "0.1.2"

  depends_on "uv" => :build
  depends_on "python@3.12"
  depends_on "openssl@4"
  depends_on "libp11"
  depends_on "opensc"
  depends_on macos: :ventura

  depends_on arch: :arm64

  on_arm do
    resource "aiohappyeyeballs" do
      url "https://files.pythonhosted.org/packages/71/43/1947f06babed6b3f1d7f38b0c767f52df66bfb2bc10b468c4a7de9eceff2/aiohappyeyeballs-2.7.1-py3-none-any.whl"
      sha256 "9243213661e29250eb41368e5daa826fc017156c3b8a11440826b2e3ed376472"
    end

    resource "aiohttp" do
      url "https://files.pythonhosted.org/packages/64/91/11b89f45ca486252dd67dd5f3231fec04bf5518da39a95cb3997619f17fb/aiohttp-3.14.5-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "d079c0a0135c36e7beb6f1c88087c8f108dc5891cdd0b5eafa778421bda70ed2"
    end

    resource "aiosignal" do
      url "https://files.pythonhosted.org/packages/fb/76/641ae371508676492379f16e2fa48f4e2c11741bd63c48be4b12a6b09cba/aiosignal-1.4.0-py3-none-any.whl"
      sha256 "053243f8b92b990551949e63930a839ff0cf0b0ebbe0597b0f3fb19e1a0fe82e"
    end

    resource "asn1crypto" do
      url "https://files.pythonhosted.org/packages/c9/7f/09065fd9e27da0eda08b4d6897f1c13535066174cc023af248fc2a8d5e5a/asn1crypto-1.5.1-py2.py3-none-any.whl"
      sha256 "db4e40728b728508912cbb3d44f19ce188f218e9eba635821bb4b68564f8fd67"
    end

    resource "attrs" do
      url "https://files.pythonhosted.org/packages/64/b4/17d4b0b2a2dc85a6df63d1157e028ed19f90d4cd97c36717afef2bc2f395/attrs-26.1.0-py3-none-any.whl"
      sha256 "c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309"
    end

    resource "certifi" do
      url "https://files.pythonhosted.org/packages/32/d1/a3652fe2c19134d0d15922177821d863cbd7e842d53a21bbe7e8e3a1b5ac/certifi-2026.10.23-py3-none-any.whl"
      sha256 "e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1"
    end

    resource "cffi" do
      url "https://files.pythonhosted.org/packages/54/7d/16e5a096677b5e313ca80cd5e5170efa3ea44624a82bb111925522da64b1/cffi-2.1.1-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "f81b3b8f3d4e343550fa4baa0e479bba9f2d29ce9c2e9b51d1ce1718d7442fcf"
    end

    resource "cryptography" do
      url "https://files.pythonhosted.org/packages/e5/56/d194340cc4a57535e82e1bee9e89667ac4b7c13b5d3f59686deae3094dd5/cryptography-50.0.2-cp311-abi3-macosx_11_0_arm64.whl"
      sha256 "fa8f5efb344d6908a1ce62f4a24e2e5780f825d6f53f5f50ec5ffacac72936cb"
    end

    resource "fonttools" do
      url "https://files.pythonhosted.org/packages/15/63/f332b2099599b4911786a6f6fd69552fdd5ae6a45cfaffb0c881092f36c8/fonttools-4.68.0-cp312-cp312-macosx_10_13_universal2.whl"
      sha256 "f265c85432c398d86f26add143423924a4747879b2dce001a3ffe0a5fed30638"
    end

    resource "frozenlist" do
      url "https://files.pythonhosted.org/packages/2b/94/5c8a2b50a496b11dd519f4a24cb5496cf125681dd99e94c604ccdea9419a/frozenlist-1.8.0-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "f833670942247a14eafbb675458b4e61c82e002a148f49e68257b79296e865c4"
    end

    resource "idna" do
      url "https://files.pythonhosted.org/packages/58/a2/bb081bab032533a855d44de1d56f8e8426114ff1ba5d1f07a438a0a654f8/idna-3.20-py3-none-any.whl"
      sha256 "ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c"
    end

    resource "lxml" do
      url "https://files.pythonhosted.org/packages/dd/1f/a180b57d9eeabaab77f9d5aa30356898ea749c4795596a8f66d1eb6bef2e/lxml-6.1.3-cp312-cp312-macosx_10_13_universal2.whl"
      sha256 "0c0710ac085a157b593c38fbcacd950f15c4afa8e2057527185875ab302752bc"
    end

    resource "multidict" do
      url "https://files.pythonhosted.org/packages/bf/e4/bd8838244fd1309165c79e74af9a6b9e9e42fd0f2c24c75bee665fc9ba69/multidict-7.2.1-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "d37773029ba034a2cc970b6eeb67dad3bff9d894393c51f6bb1c6b4f563a032c"
    end

    resource "oscrypto" do
      url "https://files.pythonhosted.org/packages/01/7c/fa07d3da2b6253eb8474be16eab2eadf670460e364ccc895ca7ff388ee30/oscrypto-1.3.0-py2.py3-none-any.whl"
      sha256 "2b2f1d2d42ec152ca90ccb5682f3e051fb55986e1b170ebde472b133713e7085"
    end

    resource "pillow" do
      url "https://files.pythonhosted.org/packages/39/4b/f2ed53d83aa44ac19599ac0a54897f867fafb95f406980d1e24083f8cbe3/pillow-13.0.0-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "fc481f742ccda20e9ed760b8f978dff50f2a4e9bc253ac167fb0a05b0783ef52"
    end

    resource "propcache" do
      url "https://files.pythonhosted.org/packages/25/88/1d7df7201750b37765ef2b23bc1c526c028dadde80afa0f57a118fc01182/propcache-0.5.4-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "87a3caecf8095e48dc72f84bfa42e23a848cf410cc9cc13031fba4869b706a21"
    end

    resource "pycparser" do
      url "https://files.pythonhosted.org/packages/b6/ae/315bbeee126a769cbde43cf4908acb4b40408d8bf8bbf334dd7368d8dadf/pycparser-3.12-py3-none-any.whl"
      sha256 "a076f3f489b39b43ed13563a1dafe42447445bec2e294154ec5c57fcdda4c85e"
    end

    resource "pyhanko-certvalidator" do
      url "https://files.pythonhosted.org/packages/e8/22/fc8a485269187b85eadd2cf536b92be403a238932e7d3943ba176fb31041/pyhanko_certvalidator-0.33.0-py3-none-any.whl"
      sha256 "72d3b830c0427a7aae45873ba7b4e34cb86caed451eff9dfb4394a69e93bb169"
    end

    resource "pyhanko" do
      url "https://files.pythonhosted.org/packages/6e/18/3c7c3c4dd7b629da4b76ba03aed2c6103ccbf280834f30dfa3d8fe47b23b/pyhanko-0.38.0-py3-none-any.whl"
      sha256 "60abfdf6114e4ad64bb413491848af4a276231b563cb9f268e8dbfbcd47e586f"
    end

    resource "pypdf" do
      url "https://files.pythonhosted.org/packages/5b/ef/11ed995bd10a1632f7fea3da38ae8d42bc3ccc5b9969fe04d8620c844408/pypdf-7.1.1-py3-none-any.whl"
      sha256 "04c5680d4b4cfa04ab505b09393fc949860c34a4dad6565284d11a2f5c3ce8b1"
    end

    resource "pypdfium2" do
      url "https://files.pythonhosted.org/packages/e7/bb/bf88a781a53c905022b25b2d1fb742c908f86b8076403471f626cc41a508/pypdfium2-5.15.2-py3-none-macosx_13_0_arm64.whl"
      sha256 "e71fe832e94421ac3c28d6a6ed4a9e61f22417089652d339f391c4ffc2a44c35"
    end

    resource "python-pkcs11" do
      url "https://files.pythonhosted.org/packages/d5/9e/f32716a4eaee82c016061fe7f5afe2530b7b7c8b777e383fef893b0ee0b5/python_pkcs11-0.9.5-cp312-cp312-macosx_10_13_universal2.whl"
      sha256 "ac6aaca5760ef3186d46bf93f34102187694d55259ac734d15ac56b1b3d5a19a"
    end

    resource "typing-extensions" do
      url "https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl"
      sha256 "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8"
    end

    resource "tzlocal" do
      url "https://files.pythonhosted.org/packages/7b/c1/9be4e1a8a30db8729a86628073910e56f85aaf8a659e053f376a2e6ea5a8/tzlocal-5.4.5-py3-none-any.whl"
      sha256 "ecab534f6d65d9deb4c4ea52c121ab6dd5958e9b878e71dcb102578269752454"
    end

    resource "uharfbuzz" do
      url "https://files.pythonhosted.org/packages/ba/05/8e4e62ee1d1f7a1060168bc5af14aa203b9d310a3eb7e97bae00d1b7dc1d/uharfbuzz-0.55.0-cp310-abi3-macosx_10_9_universal2.whl"
      sha256 "40df0ff4d0c7af29c07a8adc614fb0dd421d9c4d8a139362a80a4ceb71e94a71"
    end

    resource "uritools" do
      url "https://files.pythonhosted.org/packages/0a/ae/d9810f1b9d5eddafb5b269f51183ef8d1d59929e19a70eb11e3dfb92cc28/uritools-6.1.4-py3-none-any.whl"
      sha256 "7e48617975c3ccd3ee11da4641af8f8c9b97dcd7e75969a4cdfd7c8ce177f4e3"
    end

    resource "yarl" do
      url "https://files.pythonhosted.org/packages/be/dd/ee38aec8e09fdf957e50d4085453fbe202f56c6c3b4cf07b81cdb4f09ee9/yarl-1.25.1-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "e029648f9c951db30e98a7d7ec90835db88ec4b32820efe2a9bdc2287e032eb6"
    end

    resource "setuptools" do
      url "https://files.pythonhosted.org/packages/ef/55/6dc6d6bb953bdfc52519a0059592c52b6e3b8ad51cf8256dffceb55b0610/setuptools-84.2.1-py3-none-any.whl"
      sha256 "ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2"
    end

  end

  def install
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
