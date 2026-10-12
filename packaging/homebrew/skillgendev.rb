# Homebrew formula for skillgendev. It lives in the tap repository
# github.com/chapeee/homebrew-tap as Formula/skillgendev.rb, so people install with:
#
#   brew install chapeee/tap/skillgendev
#
# For a new release, update `url` and `sha256` (scripts/update-homebrew-formula.py does it
# from PyPI) and copy this file into the tap.
class Skillgendev < Formula
  desc "Compile an app's code into one Agent Skill per page so AI can fill its forms"
  homepage "https://github.com/chapeee/skillprinter"
  url "https://files.pythonhosted.org/packages/source/s/skillgendev/skillgendev-0.1.0.tar.gz"
  sha256 "075046edeb6fc4bf975a0a9db08358ed655703263b78599834be0c9fe9944703"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    # A private virtualenv in libexec; dependencies (Graphify, ast-grep, Playwright for
    # the probe extra) come from PyPI as wheels.
    python = Formula["python@3.12"].opt_bin/"python3.12"
    system python, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--no-cache-dir", "#{buildpath}[probe]"
    bin.install_symlink libexec/"bin/skillgendev"
  end

  def caveats
    <<~EOS
      To measure field positions with --xy, download Chromium once:
        skillgendev doctor --fix
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/skillgendev --version")
    system bin/"skillgendev", "init", "--json"
    assert_predicate testpath/".skillgendev", :directory?
  end
end
