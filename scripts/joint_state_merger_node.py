#!/usr/bin/env python3

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

"""Merge /joint_states_body and /joint_states_head into a single /joint_states topic."""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class JointStateMergerNode(Node):
    def __init__(self):
        super().__init__("joint_state_merger")

        self._body_cache: dict[str, tuple[float, float, float]] = {}
        self._head_cache: dict[str, tuple[float, float, float]] = {}

        self._pub = self.create_publisher(JointState, "joint_states", 10)

        self.create_subscription(JointState, "joint_states_body", self._on_body, 10)
        self.create_subscription(JointState, "joint_states_head", self._on_head, 10)

    def _on_body(self, msg: JointState) -> None:
        self._update_cache(self._body_cache, msg)
        self._publish(msg.header)

    def _on_head(self, msg: JointState) -> None:
        self._update_cache(self._head_cache, msg)
        self._publish(msg.header)

    @staticmethod
    def _update_cache(cache: dict, msg: JointState) -> None:
        positions = list(msg.position) + [0.0] * len(msg.name)
        velocities = list(msg.velocity) + [0.0] * len(msg.name)
        efforts = list(msg.effort) + [0.0] * len(msg.name)
        for i, name in enumerate(msg.name):
            cache[name] = (positions[i], velocities[i], efforts[i])

    def _publish(self, header) -> None:
        merged = {**self._body_cache, **self._head_cache}
        if not merged:
            return

        msg = JointState()
        msg.header = header
        msg.header.stamp = self.get_clock().now().to_msg()
        for name, (pos, vel, eff) in merged.items():
            msg.name.append(name)
            msg.position.append(pos)
            msg.velocity.append(vel)
            msg.effort.append(eff)

        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = JointStateMergerNode()
    rclpy.spin(node)
    node.destroy_node()


if __name__ == "__main__":
    main()
