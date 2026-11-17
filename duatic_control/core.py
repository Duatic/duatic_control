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

"""The core stage every robot starts first: robot description, controller manager, controllers and e-stop."""

from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from duatic_bringup_stages.stages import Stage, abort, gate


def core_stage(
    robot_description: str,
    controllers_config: str,
    *,
    namespace: str = "",
    emergency_stop_button: int = 9,
    timeout: float = 120.0,
) -> Stage:
    """
    Build the core stage. It is always required.

    The stage is ready once every controller in the config is in its configured state and every hardware
    component is active.
    """
    actions = [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            output="screen",
            parameters=[{"robot_description": robot_description}],
            remappings=[("/tf", "tf"), ("/tf_static", "tf_static")],
        ),
        Node(
            package="controller_manager",
            executable="ros2_control_node",
            parameters=[controllers_config],
            output={"stdout": "screen", "stderr": "screen"},
            on_exit=[abort("The controller manager exited")],
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution(
                    [FindPackageShare("duatic_control"), "launch", "control.launch.py"]
                )
            ),
            launch_arguments={"namespace": namespace, "config_path": controllers_config}.items(),
        ),
        Node(
            package="duatic_e_stop",
            executable="brake_release_node",
            name="brake_release_node",
            output="screen",
        ),
        Node(
            package="duatic_e_stop",
            executable="e_stop_node",
            name="e_stop_node",
            output="screen",
            parameters=[{"emergency_stop_button": emergency_stop_button}],
        ),
    ]
    return Stage(
        name="core",
        actions=actions,
        gate=gate(
            "core",
            timeout,
            controllers_config=controllers_config,
            hardware_components_active=True,
        ),
        configurable=False,
    )
