"""Isolated installer branch tests; no root, package installation or Docker needed.

Run: python3 -m unittest discover -s xray/tests -v
"""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "install-deps.sh"


class InstallerTests(unittest.TestCase):
    def shell(self, body):
        env = dict(os.environ)
        env.pop("BASH_ENV", None)
        env.pop("DOCKER_HOST", None)
        env.pop("DOCKER_CONTEXT", None)
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-c",
             "source " + shlex.quote(str(SCRIPT)) + "\n" + body],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, timeout=10,
        )

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_platform_matrix(self):
        cases = [("ubuntu", v) for v in ("20.04", "22.04", "24.04", "26.04")]
        cases += [("debian", v) for v in ("11", "12", "13")]
        for distro, version in cases:
            for arch in ("amd64", "arm64"):
                with self.subTest(distro=distro, version=version, arch=arch):
                    result = self.shell(
                        f"select_platform {distro} {version} {arch}\n"
                        'printf "%s\\n" "${DOCKER_PACKAGES[@]}" "$COMPOSE_SHA256"')
                    self.assert_ok(result)
                    self.assertIn(f"~{distro}.{version}~", result.stdout)
                    self.assertNotIn("latest", result.stdout)
                    self.assertEqual(len(result.stdout.splitlines()[-1]), 64)
                    if version == "20.04":
                        self.assertIn("containerd.io=1.7.27-1\n", result.stdout)

    def test_unknown_platforms_refused(self):
        for platform in ("ubuntu 18.04 amd64", "debian 10 amd64",
                         "ubuntu 25.04 amd64", "alpine 3.20 amd64",
                         "debian 13 armhf"):
            with self.subTest(platform=platform):
                result = self.shell("select_platform " + platform)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("不支持", result.stdout)

    def test_existing_dependency_check_and_repeat_install_are_noops(self):
        for mode in ("--check", "--dry-run", "", ""):
            with self.subTest(mode=mode):
                result = self.shell(self.ready_stubs() + f"main {mode}")
                self.assert_ok(result)
                self.assertNotIn("MUTATION", result.stdout)

    def ready_stubs(self):
        return r'''
detect_platform() { select_platform debian 13 amd64; }
ensure_root() { :; }
probe_base() { BASE_PACKAGES=(); }
probe_docker() {
    DOCKER_STATE=ready COMPOSE_STATE=ready
    DOCKER_VERSION=27.5.1 COMPOSE_VERSION=2.32.4
}
apt_run() { echo MUTATION-APT; return 88; }
setup_docker_repo() { echo MUTATION-REPO; return 88; }
systemctl() { echo MUTATION-SERVICE; return 88; }
install_compose() { echo MUTATION-COMPOSE; return 88; }
install_docker() { echo MUTATION-DOCKER; return 88; }
download() { echo MUTATION-DOWNLOAD; return 88; }
'''

    def test_check_missing_dependencies_fails_without_mutation(self):
        result = self.shell(self.ready_stubs() + r'''
probe_base() { BASE_PACKAGES=(python3 curl); }
main --check
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("依赖未就绪", result.stdout)
        self.assertNotIn("MUTATION", result.stdout)

    def test_fresh_dry_run_has_no_mutation(self):
        result = self.shell(self.ready_stubs() + r'''
probe_base() { BASE_PACKAGES=(python3); }
probe_docker() { DOCKER_STATE=absent COMPOSE_STATE=absent; }
check_fresh_install() { :; }
main --dry-run
''')
        self.assert_ok(result)
        self.assertIn("docker-ce=5:29.6.2-1~debian.13~trixie", result.stdout)
        self.assertNotIn("MUTATION", result.stdout)

    def test_missing_compose_only_adds_plugin(self):
        result = self.shell(self.ready_stubs() + r'''
added=0
probe_docker() {
    DOCKER_STATE=ready DOCKER_VERSION=24.0.9 COMPOSE_VERSION=2.35.1
    if ((added)); then COMPOSE_STATE=ready; else COMPOSE_STATE=absent; fi
}
install_compose() { added=1; echo ONLY-PLUGIN; }
main
[[ $added == 1 ]]
''')
        self.assert_ok(result)
        self.assertIn("ONLY-PLUGIN", result.stdout)
        self.assertNotIn("MUTATION", result.stdout)

    def test_stopped_docker_is_started_once(self):
        result = self.shell(self.ready_stubs() + r'''
started=0
probe_docker() {
    COMPOSE_STATE=ready DOCKER_VERSION=24.0.9 COMPOSE_VERSION=2.35.1
    if ((started)); then DOCKER_STATE=ready; else DOCKER_STATE=stopped; fi
}
check_stopped_docker() { :; }
systemctl() { [[ "$*" == 'start docker.service' ]]; ((started+=1)); }
main
[[ $started == 1 ]]
''')
        self.assert_ok(result)
        self.assertNotIn("MUTATION", result.stdout)

    def test_compose_probe_checks_daemon_compatibility(self):
        for compatible in (True, False):
            with self.subTest(compatible=compatible):
                result = self.shell(r'''
unset DOCKER_HOST
have() { [[ $1 == docker ]]; }
docker() {
    case "$*" in
        'context inspect --format {{.Endpoints.docker.Host}}') echo unix:///var/run/docker.sock ;;
        'info --format {{.ServerVersion}}') echo 29.6.2 ;;
        'compose version --short') echo 2.35.1 ;;
        'compose ls --format json') return ''' + ("0" if compatible else "1") + r''' ;;
        *) return 88 ;;
    esac
}
probe_docker
[[ $DOCKER_STATE == ready && $COMPOSE_STATE == ready ]]
''')
                if compatible:
                    self.assert_ok(result)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("已有 Compose 无法访问 Docker", result.stdout)

    def test_remote_docker_refused(self):
        result = self.shell(r'''
unset DOCKER_HOST
have() { [[ $1 == docker ]]; }
docker() { echo ssh://example.invalid; }
probe_docker
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不管理远程 Docker", result.stdout)

    def test_context_takes_precedence_over_docker_host(self):
        result = self.shell(r'''
DOCKER_CONTEXT=remote DOCKER_HOST=unix:///var/run/docker.sock
have() { [[ $1 == docker ]]; }
docker() { [[ "$*" == 'context inspect remote --format {{.Endpoints.docker.Host}}' ]]; echo ssh://example.invalid; }
probe_docker
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不管理远程 Docker", result.stdout)

    def test_conflicting_runtime_refused(self):
        result = self.shell(r'''
package_installed() { [[ $1 == containerd ]]; }
check_fresh_install
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不自动替换或卸载", result.stdout)

    def test_unavailable_pin_never_falls_back_to_latest(self):
        result = self.shell(r'''
select_platform ubuntu 20.04 amd64
apt-cache() { echo 'docker-ce | 5:99.0.0-1~ubuntu.20.04~focal | example'; }
check_pinned_packages
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少固定包 docker-ce=5:28.1.1", result.stdout)

    def test_apt_uses_noninteractive_no_restart_environment(self):
        result = self.shell(r'''
apt-get() {
    [[ $DEBIAN_FRONTEND == noninteractive && $NEEDRESTART_MODE == l ]]
    printf '%s\n' "$*"
}
apt_run install -y --no-install-recommends --no-remove python3
''')
        self.assert_ok(result)
        self.assertIn("--no-remove python3", result.stdout)

    def test_fresh_install_pins_packages_and_does_not_restart_docker(self):
        result = self.shell(r'''
select_platform ubuntu 20.04 amd64
setup_docker_repo() { :; }
apt_update() { :; }
check_pinned_packages() { :; }
apt_run() { printf 'APT: %s\n' "$*"; }
bounded() { return 0; }
systemctl() { [[ "$*" == 'enable docker.service' ]]; }
install_docker
''')
        self.assert_ok(result)
        self.assertIn("--no-remove docker-ce=5:28.1.1-1~ubuntu.20.04~focal", result.stdout)
        self.assertIn("docker-ce-cli=5:28.1.1-1~ubuntu.20.04~focal", result.stdout)
        self.assertIn("containerd.io=1.7.27-1", result.stdout)
        self.assertIn("docker-compose-plugin=2.35.1-1~ubuntu.20.04~focal", result.stdout)

    def test_compose_checksum_and_existing_file_protection(self):
        for situation in ("valid", "bad-hash", "existing", "symlink"):
            with self.subTest(situation=situation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                binary = b'#!/usr/bin/env bash\necho 2.35.1\n'
                source = root / "download"
                source.write_bytes(binary)
                work = root / "work"
                work.mkdir()
                plugin = root / "plugins" / "docker-compose"
                plugin.parent.mkdir()
                if situation == "existing":
                    plugin.write_bytes(b"keep existing plugin")
                if situation == "symlink":
                    plugin.symlink_to(root / "missing")
                digest = hashlib.sha256(binary).hexdigest() if situation != "bad-hash" else "0" * 64
                result = self.shell(
                    'select_platform debian 13 amd64\n'
                    f'WORK_DIR={shlex.quote(str(work))}\n'
                    f'COMPOSE_SHA256={digest}\n'
                    'download() { cp ' + shlex.quote(str(source)) + ' "$2"; }\n'
                    f'install_compose {shlex.quote(str(plugin.parent))}\n')
                if situation == "valid":
                    self.assert_ok(result)
                    self.assertEqual(plugin.read_bytes(), binary)
                    self.assertEqual(plugin.stat().st_mode & 0o777, 0o755)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    if situation == "existing":
                        self.assertEqual(plugin.read_bytes(), b"keep existing plugin")
                    elif situation == "symlink":
                        self.assertTrue(plugin.is_symlink())
                    else:
                        self.assertFalse(plugin.exists())
                self.assertFalse(list(plugin.parent.glob(".xray-compose.*")))


if __name__ == "__main__":
    unittest.main()
