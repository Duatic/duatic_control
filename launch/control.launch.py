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

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.conditions import UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    config_path = LaunchConfiguration("config_path").perform(context)

    # Load YAML
    with open(config_path) as f:
        data = yaml.safe_load(f)

    # Get controller manager section
    try:
        cm_params = data["/**"]["controller_manager"]["ros__parameters"]
        print(f"Controller Manager parameters:\n{yaml.dump(cm_params, sort_keys=False)}")
    except KeyError:
        print("Could not find '/**/controller_manager/ros__parameters' in the YAML file.")
        return []

    # Extract controller manager parameters (update_rate, hardware_components_initial_state)
    cm_parameters = []
    update_rate = cm_params.pop("update_rate", 1000)
    if update_rate is not None:
        cm_parameters.append({"update_rate": update_rate})
    hardware_components_initial_state = cm_params.pop("hardware_components_initial_state", {})
    if hardware_components_initial_state:
        cm_parameters.append(
            {"hardware_components_initial_state": hardware_components_initial_state}
        )

    # Controller Manager Node
    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=cm_parameters,
        output={"stdout": "screen", "stderr": "screen"},
        condition=UnlessCondition(LaunchConfiguration("use_sim_time")),
    )

    # Identify controllers, states, and remappings
    controllers = []

    for controller_name in list(cm_params.keys()):
        controller_params = cm_params[controller_name]

        # Check validation (type is mandatory for the controller manager)
        if isinstance(controller_params, dict) and "type" in controller_params:

            # We use .pop() so these don't get uploaded to the ROS parameter server
            ctrl_state = controller_params.pop("state", "active").lower()
            ctrl_remappings = controller_params.pop("remappings", {})

            controllers.append((controller_name, ctrl_state, ctrl_remappings))

    # Configure controllers
    spawner_nodes = []
    for controller_name, state, remappings in controllers:
        args = [
            controller_name,
            "-c",
            "controller_manager",
            "--switch-timeout",
            "30.0",
            "--param-file",
            config_path,
            "--inactive",
        ]

        # Handle Remappings
        if remappings:
            for from_topic, to_topic in remappings.items():
                args.append("--controller-ros-args")
                args.append(f"--remap {from_topic}:={to_topic}")

        node = Node(
            package="controller_manager",
            executable="spawner",
            namespace=LaunchConfiguration("namespace").perform(context),
            arguments=args,
            output="screen",
        )
        spawner_nodes.append(node)

    # Parameter loader node
    target_node = "/controller_manager"
    if LaunchConfiguration("namespace").perform(context) != "":
        target_node = (
            "/" + LaunchConfiguration("namespace").perform(context) + "/controller_manager"
        )
    load_params = Node(
        package="duatic_control",
        executable="param_loader_node.py",
        name="param_loader",
        output="screen",
        parameters=[
            {
                "target_node": target_node,
                "parameters": yaml.dump(cm_params),
            }
        ],
    )

    # Chain: param_loader -> spawner[0] -> spawner[1] -> … -> hardware activator -> controller activator
    prev = load_params
    event_handlers = []
    for spawner_node in spawner_nodes:
        event_handlers.append(
            RegisterEventHandler(OnProcessExit(target_action=prev, on_exit=[spawner_node]))
        )
        prev = spawner_node

    active_names = [name for name, state, _ in controllers if state == "active"]
    inactive_components = hardware_components_initial_state.get("inactive", [])

    # Hardware must be active before its command interfaces can be claimed.
    if inactive_components:
        hardware_activator = Node(
            package="duatic_control",
            executable="hardware_activator_node.py",
            name="hardware_activator",
            output="screen",
            parameters=[
                {
                    "controller_manager": target_node,
                    "hardware_components": inactive_components,
                }
            ],
        )
        event_handlers.append(
            RegisterEventHandler(OnProcessExit(target_action=prev, on_exit=[hardware_activator]))
        )
        prev = hardware_activator

    if active_names:
        controller_activator = Node(
            package="duatic_control",
            executable="controller_activator_node.py",
            name="controller_activator",
            output="screen",
            parameters=[
                {
                    "controllers": active_names,
                    "controller_manager": target_node,
                }
            ],
        )
        event_handlers.append(
            RegisterEventHandler(OnProcessExit(target_action=prev, on_exit=[controller_activator]))
        )

    return [controller_manager, load_params] + event_handlers


def generate_launch_description():
    declared_arguments = [
        DeclareLaunchArgument(
            "config_path", default_value="", description="Path to the controller config YAML file."
        ),
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
    ]

    # Add nodes to LaunchDescription
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
