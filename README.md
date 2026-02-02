# Duatic Control
[![ROS2](https://img.shields.io/badge/ROS2-Jazzy-blue.svg)](https://docs.ros.org/en/jazzy/)
[![License](https://img.shields.io/badge/License-Duatic-blue.svg)](LICENSE)

Compact ros2_control integration for Duatic robots.

## Overview
- The URDF plugin (urdf/plugins.urdf.xacro) expects a full path to a controllers YAML file.
- That YAML must contain the controller_manager and controller node parameter mappings using the top-level wildcard `/**:` so the ros2_control plugin can load controllers on startup.

## Quick usage
- Ensure a config file exists and pass its absolute path to the launch/spawn process that loads the URDF plugin.

Example:
```bash
ros2 launch duatic_control control.launch.py \
  namespace:="robot1" \
  controllers_file:="/full/path/to/controllers.yaml"
```

## Config file format
- File must be valid YAML.
- Top-level must use `/**:` to scope parameters for controller_manager and named controllers.
- Each controller definition can include:
  - `type`: (required) The controller plugin type (e.g., `joint_state_broadcaster/JointStateBroadcaster`).
  - `state`: (optional) Activation status on startup. Use `active` (default) or `inactive`.
  - `remappings`: (optional) A dictionary of topic remappings in the format `topic_name: remapped_topic_name`.

Example:
```yaml
/**:
  controller_manager:
    ros__parameters:
      update_rate: 100
      joint_state_broadcaster:
        type: joint_state_broadcaster/JointStateBroadcaster
        state: active
      mecanum_drive_controller:
        type: mecanum_drive_controller/MecanumDriveController
        state: active
        remappings:
          mecanum_drive_controller/reference: cmd_vel
      gravity_compensation_controller_arm_right:
        type: dynaarm_controllers/GravityCompensationController
        state: inactive

  mecanum_drive_controller:
    ros__parameters:
      reference_timeout: 0.7
      front_left_wheel_command_joint_name: "joint_wheel1"
      front_right_wheel_command_joint_name: "joint_wheel2"
      rear_right_wheel_command_joint_name: "joint_wheel3"
      rear_left_wheel_command_joint_name: "joint_wheel4"
      kinematics:
        wheels_radius: 0.1015
        sum_of_robot_center_projection_on_X_Y_axis: 0.595
      enable_odom_tf: false
      base_frame_id: "base_link"
```

## URDF plugin (for usage with Gazebo Sim)
- Macro parameters: `namespace`, `controllers_file` (absolute path required).
- The plugin reads the config file and injects it into the ros2_control controller_manager on spawn, the config file must be the same that's passed to the control.launch.py file.

Example:
```xml
<xacro:include filename="$(find duatic_control)/urdf/plugins.urdf.xacro" />
<xacro:control namespace="$(arg namespace)" controllers_file="$(find platform_bringup)/config/controllers.yaml"/>
```

## Troubleshooting
- If controllers don't load: validate YAML syntax, ensure `/**:` is present, and confirm the launch passes an absolute path to the controllers file.
