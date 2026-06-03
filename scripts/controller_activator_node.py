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

"""Activate ROS 2 controllers through the controller manager."""

import rclpy
from rclpy.node import Node
from controller_manager_msgs.srv import SwitchController


class ControllerActivatorNode(Node):
    """Activate a configured set of controllers.

    The node reads controller names from the ``controllers`` parameter and sends
    them in one strict ``switch_controller`` request to the configured controller
    manager.

    Attributes:
        controllers: Names of controllers to activate.
        cm_name: Controller manager node name or namespace.
    """

    def __init__(self):
        """Initialize the node and read controller activation parameters."""
        super().__init__("controller_activator")

        self.declare_parameter("controllers", [""])
        self.declare_parameter("controller_manager", "/controller_manager")

        self.controllers = [
            c
            for c in self.get_parameter("controllers").get_parameter_value().string_array_value
            if c
        ]
        self.cm_name = self.get_parameter("controller_manager").get_parameter_value().string_value

    def _wait_for_service(self, client, name):
        """Wait for a ROS service to become available.

        Args:
            client: ROS service client to wait on.
            name: Human-readable service name used in log messages.

        Returns:
            True if the service becomes available before timeout, otherwise False.
        """
        attempts = 0
        while not client.wait_for_service(timeout_sec=1.0):
            attempts += 1
            if attempts > 20:
                self.get_logger().error(f"Timeout waiting for {name} service.")
                return False
            self.get_logger().warn(f"Waiting for {name} service... (attempt {attempts})")
        return True

    def _call(self, client, req):
        """Call a ROS service synchronously using a spin loop.

        Args:
            client: ROS service client used to send the request.
            req: Service request message.

        Returns:
            The service response, or None if the call fails.
        """
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def activate_controllers(self):
        """Activate all configured controllers.

        Returns:
            True if there are no controllers to activate or activation succeeds,
            otherwise False.
        """
        if not self.controllers:
            self.get_logger().info("No controllers to activate.")
            return True

        client = self.create_client(SwitchController, f"{self.cm_name}/switch_controller")
        if not self._wait_for_service(client, "switch_controller"):
            return False

        self.get_logger().info(f"Activating controllers: {self.controllers}")
        req = SwitchController.Request()
        req.activate_controllers = self.controllers
        req.strictness = SwitchController.Request.STRICT
        req.activate_asap = True

        result = self._call(client, req)
        if result is None or not result.ok:
            self.get_logger().error(f"Failed to activate controllers: {self.controllers}")
            return False
        self.get_logger().info(f"Successfully activated controllers: {self.controllers}")
        return True

    def run(self):
        """Run the one-shot controller activation workflow."""
        self.activate_controllers()


def main(args=None):
    """Run the controller activator node.

    Args:
        args: Optional ROS command-line arguments.
    """
    rclpy.init(args=args)
    node = ControllerActivatorNode()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
