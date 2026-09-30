"""Exercise resume with real curl and an isolated HTTPS server; no public downloads.

Run: python3 -m unittest discover -s xray/tests -p test_install_client.py -v
Requires Linux, bash, curl, python3, coreutils and openssl; never installs services.
"""
import hashlib
import http.server
import io
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "install-client.sh"
CHUNK = 16384


class DownloadHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        state = self.server.state
        offset_header = self.headers.get("Range")
        state["requests"].append(offset_header)
        mode = state["mode"]
        if mode == "not_found" or (mode == "busy_once" and len(state["requests"]) == 1):
            self.send_response(404 if mode == "not_found" else 503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = state["payload"]
        if offset_header and mode == "reject_range":
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % len(payload))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        offset = int(offset_header[6:-1]) if offset_header else 0
        if mode == "ignore_range":
            offset = 0
        self.send_response(206 if offset else 200)
        self.send_header("Content-Length", str(len(payload) - offset))
        if offset:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (
                offset, len(payload) - 1, len(payload)))
        self.end_headers()
        drop = mode in ("drop_always", "stall") or (
            mode == "drop_once" and len(state["requests"]) == 1)
        try:
            self.wfile.write(payload[offset:offset + CHUNK] if drop else payload[offset:])
            self.wfile.flush()
            if mode == "stall":
                state["release"].wait(10)
            if drop:
                self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  # Expected when curl rejects a range or is interrupted.


@unittest.skipUnless(platform.system() == "Linux" and shutil.which("openssl"),
                     "requires Linux and openssl")
class ClientDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certs = tempfile.TemporaryDirectory(prefix="xray-test-tls-")
        cls.addClassCleanup(cls.certs.cleanup)
        cert_dir = Path(cls.certs.name)
        cls.cert = cert_dir / "cert.pem"
        cls.key = cert_dir / "key.pem"
        config = cert_dir / "openssl.cnf"
        config.write_text("[req]\ndistinguished_name=dn\nx509_extensions=ext\n"
                          "prompt=no\n[dn]\nCN=localhost\n[ext]\n"
                          "subjectAltName=IP:127.0.0.1\n", encoding="utf-8")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-config", str(config), "-keyout", str(cls.key),
                        "-out", str(cls.cert)], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
        cls.binary = b"#!/bin/sh\nprintf 'fixture-xray\\n'\n#" + b"x" * (CHUNK * 16) + b"\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("xray", cls.binary)
        cls.payload = buf.getvalue()

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="xray-client-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = {"mode": "ok", "requests": [], "payload": self.payload,
                      "release": threading.Event()}
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), DownloadHandler)
        self.server.state = self.state
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.cert), str(self.key))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        thread = threading.Thread(target=self.server.serve_forever,
                                  kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.state["release"].set)
        # Change only the URL and pinned digest in a private fixture copy.
        source = SCRIPT.read_text(encoding="utf-8")
        url = "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/${archive}"
        self.assertEqual(source.count(url), 1)
        source = source.replace(url, "https://127.0.0.1:%d/archive.zip" %
                                self.server.server_port)
        source, count = re.subn(r"expected_sha256='[a-f0-9]{64}'",
                               "expected_sha256='%s'" % hashlib.sha256(self.payload).hexdigest(),
                               source)
        self.assertEqual(count, 2)
        self.script = self.root / "install-client.sh"
        self.script.write_text(source, encoding="utf-8")
        self.env = {key: value for key, value in os.environ.items()
                    if not key.lower().endswith("_proxy") and
                    key not in ("BASH_ENV", "ENV", "XDG_CACHE_HOME", "CURL_HOME")}
        # Cache, extraction and installation all use isolated temporary paths.
        self.env.update(XDG_CACHE_HOME=str(self.root / "cache with spaces"),
                        CURL_CA_BUNDLE=str(self.cert), NO_PROXY="*", no_proxy="*",
                        TMPDIR=str(self.root / "tmp"))
        Path(self.env["TMPDIR"]).mkdir()
        arch = platform.machine()
        names = {"x86_64": "Xray-linux-64.zip", "amd64": "Xray-linux-64.zip",
                 "aarch64": "Xray-linux-arm64-v8a.zip", "arm64": "Xray-linux-arm64-v8a.zip"}
        if arch not in names:
            self.skipTest("unsupported installer architecture")
        version = re.search(r"XRAY_VERSION='([^']+)'", source).group(1)
        self.cache = Path(self.env["XDG_CACHE_HOME"]) / "xray-client" / (
            "v" + version) / names[arch]
        self.target = self.root / "install with spaces"

    def seed(self, data):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_bytes(data)

    def run_installer(self):
        return subprocess.run(["bash", str(self.script), str(self.target)], env=self.env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=20)

    def assert_installed(self, result):
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.target / "xray").read_bytes(), self.binary)
        self.assertEqual(self.cache.read_bytes(), self.payload)
        self.assertEqual(list(Path(self.env["TMPDIR"]).iterdir()), [])

    def test_automatic_retry_resumes_partial_response(self):
        self.state["mode"] = "drop_once"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"], [None, "bytes=%d-" % CHUNK])

    def test_retry_exhaustion_keeps_progress_for_next_run(self):
        self.state["mode"] = "drop_always"
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.cache.read_bytes(), self.payload[:CHUNK * 4])
        self.assertEqual(self.state["requests"], [None] + [
            "bytes=%d-" % (CHUNK * n) for n in (1, 2, 3)])
        self.state["mode"] = "ok"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"][-1], "bytes=%d-" % (CHUNK * 4))

    def test_timeout_keeps_progress_for_next_run(self):
        # Shorten the fixture's transfer deadline to exercise timeout without waiting 30 min.
        source = self.script.read_text(encoding="utf-8")
        self.assertIn("--max-time 1800", source)
        self.script.write_text(source.replace("--max-time 1800", "--max-time 1"),
                               encoding="utf-8")
        self.state["mode"] = "stall"
        result = self.run_installer()
        self.assertEqual(result.returncode, 28, result.stdout)
        self.assertEqual(self.cache.read_bytes(), self.payload[:CHUNK * 4])
        self.assertFalse(self.target.exists())
        self.state["release"].set()
        self.state["mode"] = "ok"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"][-1], "bytes=%d-" % (CHUNK * 4))

    def test_verified_cache_needs_no_network(self):
        self.seed(self.payload)
        self.state["mode"] = "not_found"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"], [])

    def test_server_ignoring_range_restarts_safely(self):
        self.seed(self.payload[:CHUNK])
        self.state["mode"] = "ignore_range"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"], ["bytes=%d-" % CHUNK, None])

    def test_unsatisfiable_range_restarts_safely(self):
        self.seed(b"x" * (len(self.payload) + 1))
        self.state["mode"] = "reject_range"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"], [
            "bytes=%d-" % (len(self.payload) + 1), None])

    def test_corrupt_partial_is_never_installed(self):
        self.seed(b"x" * CHUNK)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("SHA-256", result.stdout)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.cache.exists())
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"][-1], None)

    def test_http_404_preserves_partial_without_retries(self):
        self.seed(self.payload[:CHUNK])
        self.state["mode"] = "not_found"
        result = self.run_installer()
        self.assertEqual(result.returncode, 22, result.stdout)
        self.assertEqual(self.cache.read_bytes(), self.payload[:CHUNK])
        self.assertEqual(len(self.state["requests"]), 1)

    def test_http_503_retries_without_losing_progress(self):
        self.seed(self.payload[:CHUNK])
        self.state["mode"] = "busy_once"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"], ["bytes=%d-" % CHUNK] * 2)

    def start_stalled_download(self):
        self.state["mode"] = "stall"
        process = subprocess.Popen(["bash", str(self.script), str(self.target)], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, start_new_session=True)
        def stop():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=5)
        self.addCleanup(stop)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.cache.exists() and self.cache.stat().st_size == CHUNK:
                return process
            if process.poll() is not None:
                self.fail(process.communicate()[0])
            time.sleep(0.02)
        self.fail("download did not produce a partial cache")

    def stop_and_resume(self, process, sig):
        os.killpg(process.pid, sig)
        output, _ = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 128 + sig, output)
        self.assertEqual(self.cache.read_bytes(), self.payload[:CHUNK])
        self.assertEqual(len(self.state["requests"]), 1)
        self.state["release"].set()
        self.state["mode"] = "ok"
        self.assert_installed(self.run_installer())
        self.assertEqual(self.state["requests"][-1], "bytes=%d-" % CHUNK)

    def test_ctrl_c_preserves_cache_and_releases_lock(self):
        self.stop_and_resume(self.start_stalled_download(), signal.SIGINT)

    def test_concurrent_install_is_refused_and_term_preserves_cache(self):
        process = self.start_stalled_download()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("另一个安装进程", result.stdout)
        self.assertEqual(len(self.state["requests"]), 1)
        self.stop_and_resume(process, signal.SIGTERM)

    def test_existing_binary_is_not_overwritten(self):
        self.target.mkdir()
        installed = self.target / "xray"
        installed.write_bytes(b"existing-binary")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(installed.read_bytes(), b"existing-binary")
        self.assertEqual(self.state["requests"], [])


if __name__ == "__main__":
    unittest.main()
