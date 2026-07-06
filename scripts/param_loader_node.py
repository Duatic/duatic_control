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

"""Load ROS 2 parameters from YAML and set them on a target node."""

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.srv import SetParameters
import yaml


class ParamLoaderNode(Node):
    """Load nested parameters into another running ROS 2 node.

    The node accepts either a YAML file path through ``param_file`` or a YAML
    string through ``parameters``. Nested YAML dictionaries are flattened into
    dotted ROS parameter names before being sent to the target node's
    ``set_parameters`` service.

    Attributes:
        target_node: Fully qualified name of the node receiving parameters.
        params: Parsed YAML parameters to send to the target node.
        client: Client for the target node's ``set_parameters`` service.
        timer: Timer that retries the service lookup until it is available.
        attempts: Number of service lookup attempts already made.
    """

    def __init__(self):
        """Initialize the loader node and parse the configured parameter source."""
        super().__init__("param_loader")

        self.get_logger().info("🚀ParamLoaderNode started")
        # Declare parameters
        self.declare_parameter("target_node", "")
        self.declare_parameter("param_file", "")
        self.declare_parameter("parameters", "")

        self.target_node = self.get_parameter("target_node").get_parameter_value().string_value
        param_file = self.get_parameter("param_file").get_parameter_value().string_value
        parameters_str = self.get_parameter("parameters").get_parameter_value().string_value

        # Load parameters from file or YAML string
        self.params = {}
        if param_file:
            try:
                with open(param_file) as f:
                    self.params = yaml.safe_load(f)
            except Exception as e:
                self.get_logger().error(f"Failed to load YAML file '{param_file}': {e}")
                rclpy.shutdown()
                return
        elif parameters_str:
            try:
                self.params = yaml.safe_load(parameters_str)
            except Exception as e:
                self.get_logger().error(f"Failed to parse 'parameters': {e}")
                rclpy.shutdown()
                return
        else:
            self.get_logger().error("No parameters provided (need 'param_file' or 'parameters').")
            rclpy.shutdown()
            return

        if not self.target_node:
            self.get_logger().error("Missing required parameter: 'target_node'")
            rclpy.shutdown()
            return

        self.get_logger().info(f"Loading parameters into {self.target_node}")

        self.client = self.create_client(SetParameters, f"{self.target_node}/set_parameters")
        self.timer = self.create_timer(0.5, self.try_set_parameters)
        self.attempts = 0

    def flatten_params(self, prefix, data):
        """Flatten nested parameter dictionaries into ROS-style names.

        Args:
            prefix: Dotted prefix to prepend to every parameter name.
            data: Nested dictionary of parameter names and values.

        Returns:
            A list of ROS parameter messages ready for ``SetParameters``.
        """
        flat = []
        for key, value in data.items():
            full_name = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.extend(self.flatten_params(full_name, value))
            else:
                flat.append(Parameter(name=full_name, value=value).to_parameter_msg())
        return flat

    def try_set_parameters(self):
        """Wait for the target service, then send all loaded parameters."""
        if not self.client.wait_for_service(timeout_sec=1.0):
            self.attempts += 1
            if self.attempts > 20:
                self.get_logger().error(
                    f"Timeout waiting for {self.target_node}/set_parameters service."
                )
                rclpy.shutdown()
            else:
                self.get_logger().warn(
                    f"Waiting for {self.target_node}/set_parameters... (attempt {self.attempts})"
                )
            return

        param_list = self.flatten_params("", self.params)
        self.get_logger().info(f"Setting {len(param_list)} parameters on {self.target_node}...")

        req = SetParameters.Request(parameters=param_list)
        future = self.client.call_async(req)
        future.add_done_callback(self.on_done)
        self.timer.cancel()

    def on_done(self, future):
        """Handle completion of the asynchronous ``SetParameters`` request.

        Args:
            future: Future returned by the asynchronous service call.
        """
        try:
            result = future.result()
            if result and all(r.successful for r in result.results):
                self.get_logger().info(f"Parameters successfully set on {self.target_node}")
            else:
                for i, r in enumerate(result.results):
                    if not r.successful:
                        self.get_logger().error(f"Parameter {i} failed: {r.reason}")
        except Exception as e:
            self.get_logger().error(f"Exception while setting parameters: {e}")
        finally:
            rclpy.shutdown()


def main(args=None):
    """Run the parameter loader node.

    Args:
        args: Optional ROS command-line arguments.
    """
    rclpy.init(args=args)
    node = ParamLoaderNode()
    rclpy.spin(node)
    node.destroy_node()


if __name__ == "__main__":
    main()
