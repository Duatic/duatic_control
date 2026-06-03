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

"""Activate ROS 2 control hardware components through the controller manager."""

import rclpy
from rclpy.node import Node
from lifecycle_msgs.msg import State
from controller_manager_msgs.srv import (
    SetHardwareComponentState,
    ListHardwareComponents,
)


class HardwareActivatorNode(Node):
    """Bring requested hardware components to the active lifecycle state.

    The node reads hardware component names from the ``hardware_components``
    parameter and activates each component through the configured controller
    manager. Components that are still unconfigured are first transitioned to
    inactive, then active.

    Attributes:
        cm_name: Controller manager node name or namespace.
        hardware_components: Names of hardware components to activate.
    """

    def __init__(self):
        """Initialize the node and read hardware activation parameters."""
        super().__init__("hardware_activator")

        self.declare_parameter("controller_manager", "/controller_manager")
        self.declare_parameter("hardware_components", [""])

        self.cm_name = self.get_parameter("controller_manager").get_parameter_value().string_value
        self.hardware_components = [
            h
            for h in self.get_parameter("hardware_components")
            .get_parameter_value()
            .string_array_value
            if h
        ]

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

    def activate_hardware(self):
        """Transition the requested hardware components to the active state.

        Returns:
            True if all configured components are active or activation succeeds,
            otherwise False.
        """
        if not self.hardware_components:
            self.get_logger().info(
                "No hardware components configured for activation; skipping hardware activation."
            )
            return True

        list_client = self.create_client(
            ListHardwareComponents, f"{self.cm_name}/list_hardware_components"
        )
        set_client = self.create_client(
            SetHardwareComponentState, f"{self.cm_name}/set_hardware_component_state"
        )
        if not self._wait_for_service(
            list_client, "list_hardware_components"
        ) or not self._wait_for_service(set_client, "set_hardware_component_state"):
            return False

        components = self._call(list_client, ListHardwareComponents.Request())
        if components is None:
            self.get_logger().error("Failed to list hardware components.")
            return False

        states = {c.name: c.state.id for c in components.component}

        ok = True
        for name in self.hardware_components:
            current = states.get(name)
            if current is None:
                self.get_logger().error(f"Hardware component '{name}' not found.")
                ok = False
                continue
            if current == State.PRIMARY_STATE_ACTIVE:
                self.get_logger().info(f"Hardware component '{name}' already active.")
                continue

            # If the component is still unconfigured, configure it first, then activate.
            if current == State.PRIMARY_STATE_UNCONFIGURED:
                if not self._set_hardware_state(
                    set_client, name, State.PRIMARY_STATE_INACTIVE, "inactive"
                ):
                    ok = False
                    continue

            if not self._set_hardware_state(set_client, name, State.PRIMARY_STATE_ACTIVE, "active"):
                ok = False

        return ok

    def _set_hardware_state(self, client, name, state_id, label):
        """Set one hardware component to a requested lifecycle state.

        Args:
            client: Client for ``set_hardware_component_state``.
            name: Hardware component name.
            state_id: Lifecycle state ID from ``lifecycle_msgs.msg.State``.
            label: Lifecycle state label used in the request and log messages.

        Returns:
            True if the controller manager reports success, otherwise False.
        """
        req = SetHardwareComponentState.Request()
        req.name = name
        req.target_state = State(id=state_id, label=label)
        result = self._call(client, req)
        if result is None or not result.ok:
            self.get_logger().error(f"Failed to set '{name}' to '{label}'.")
            return False
        self.get_logger().info(f"Hardware component '{name}' -> '{label}'.")
        return True

    def run(self):
        """Run the one-shot hardware activation workflow."""
        if not self.activate_hardware():
            self.get_logger().error("Aborting: hardware activation failed.")


def main(args=None):
    """Run the hardware activator node.

    Args:
        args: Optional ROS command-line arguments.
    """
    rclpy.init(args=args)
    node = HardwareActivatorNode()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
