# Homebrew Formula for os-manager CLI (osm)
class Osm < Formula
  desc "Autonomous governance harness and control plane for Claude Code"
  homepage "https://github.com/0xrizz/os-manager"
  url "https://github.com/0xrizz/os-manager/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  license "MIT"

  depends_on "python@3.11"
  depends_on "bubblewrap" => :recommended

  def install
    virtualenv_install_with_resources
    bin.install_symlink libexec/"bin/osm" => "osm"
  end

  test do
    assert_match "osm", shell_output("#{bin}/osm --version")
  end
end
