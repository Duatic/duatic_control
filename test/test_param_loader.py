# Copyright 2026 Duatic AG
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that
# the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions, and
#    the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions, and
#    the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or
#    promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""Exit codes of the param loader."""

import subprocess
import sys
import threading
from pathlib import Path

import rclpy
from rclpy.parameter import Parameter

LOADER = str(Path(__file__).resolve().parent.parent / "scripts" / "param_loader_node.py")


def run_loader(target_node, param_file, timeout=60.0):
    return subprocess.run(
        [
            sys.executable,
            LOADER,
            "--ros-args",
            "-p",
            f"target_node:={target_node}",
            "-p",
            f"param_file:={param_file}",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class Target:
    """A node with one integer parameter, spinning in the background."""

    def __enter__(self):
        rclpy.init()
        self.node = rclpy.create_node("test_target")
        self.node.declare_parameter("rate", 5)
        self.thread = threading.Thread(target=rclpy.spin, args=(self.node,), daemon=True)
        self.thread.start()
        return self.node

    def __exit__(self, *_):
        rclpy.shutdown()
        self.thread.join()


def test_loaded_parameters_pass(tmp_path):
    params = tmp_path / "params.yaml"
    params.write_text("rate: 7\n")
    with Target() as node:
        result = run_loader("/test_target", params)
        assert node.get_parameter("rate").value == 7
    assert result.returncode == 0


def test_rejected_parameter_fails_and_is_named(tmp_path):
    params = tmp_path / "params.yaml"
    params.write_text("rate: fast\n")
    with Target() as node:
        result = run_loader("/test_target", params)
        assert node.get_parameter("rate").type_ == Parameter.Type.INTEGER
    assert result.returncode == 1
    assert "rejected parameter 'rate'" in result.stdout + result.stderr


def test_missing_target_fails(tmp_path):
    params = tmp_path / "params.yaml"
    params.write_text("rate: 7\n")
    result = run_loader("/no_such_node", params)
    assert result.returncode == 1
    assert "Timeout waiting for /no_such_node/set_parameters" in result.stdout + result.stderr
