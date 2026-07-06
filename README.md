# Duatic Control
[![Humble](https://github.com/Duatic/duatic_control/actions/workflows/build-humble.yml/badge.svg?branch=main)](https://github.com/Duatic/duatic_control/actions/workflows/build-humble.yml)
[![Jazzy](https://github.com/Duatic/duatic_control/actions/workflows/build-jazzy.yml/badge.svg?branch=main)](https://github.com/Duatic/duatic_control/actions/workflows/build-jazzy.yml)
[![Kilted](https://github.com/Duatic/duatic_control/actions/workflows/build-kilted.yml/badge.svg?branch=main)](https://github.com/Duatic/duatic_control/actions/workflows/build-kilted.yml)
[![Lyrical](https://github.com/Duatic/duatic_control/actions/workflows/build-lyrical.yml/badge.svg?branch=main)](https://github.com/Duatic/duatic_control/actions/workflows/build-lyrical.yml)
[![Rolling](https://github.com/Duatic/duatic_control/actions/workflows/build-rolling.yml/badge.svg?branch=main)](https://github.com/Duatic/duatic_control/actions/workflows/build-rolling.yml)

Compact `ros2_control` integration for Duatic robots.

## Overview

This package provides:

- `launch/control.launch.py`, a common launch sequence for controller manager setup and controller activation.
- `scripts/param_loader_node.py`, which loads nested controller parameters into a running controller manager.
- `scripts/hardware_activator_node.py`, which activates hardware components listed as initially inactive.
- `scripts/controller_activator_node.py`, which activates all requested controllers in one strict `switch_controller` call.
- `urdf/plugins.urdf.xacro`, a Gazebo Sim `gz_ros2_control` plugin macro.

The launch sequence is intentionally staged:

1. Start `ros2_control_node` unless `use_sim_time:=true`.
2. Load controller manager and controller parameters from the YAML file.
3. Spawn every configured controller inactive.
4. Activate hardware components listed under `hardware_components_initial_state.inactive`.
5. Activate controllers whose config metadata has `state: active`.

This keeps hardware writes disabled until controllers have been loaded and configured, while still activating command-claiming controllers only after their hardware interfaces are available.

## Quick Usage

Pass the controller config with the `config_path` launch argument:

```bash
ros2 launch duatic_control control.launch.py \
  namespace:=robot1 \
  config_path:=/full/path/to/controllers.yaml
```

For Gazebo Sim, run the same launch file with `use_sim_time:=true`. In that mode `control.launch.py` does not start `ros2_control_node`; the Gazebo plugin owns the controller manager.

```bash
ros2 launch duatic_control control.launch.py \
  namespace:=robot1 \
  config_path:=/full/path/to/controllers_sim.yaml \
  use_sim_time:=true
```

## Launch Arguments

- `config_path`: Path to the controller config YAML file.
- `namespace`: Optional namespace for controller manager, spawners, and activation nodes.
- `use_sim_time`: When `false`, launch `controller_manager/ros2_control_node`. When `true`, skip it for Gazebo Sim.

## Config File Format

The config file must be valid YAML and must use `/**:` as the top-level scope:

```yaml
/**:
  controller_manager:
    ros__parameters:
      update_rate: 1000

      hardware_components_initial_state:
        inactive:
          - DuaTorsoSystem

      joint_state_broadcaster:
        type: joint_state_broadcaster/JointStateBroadcaster
        state: active

      gravity_compensation_controller:
        type: duatic_controllers/GravityCompensationController
        state: active

      joint_trajectory_controller_arm_left:
        type: joint_trajectory_controller/JointTrajectoryController
        state: inactive

  joint_state_broadcaster:
    ros__parameters:
      use_urdf_to_filter: false
      joints:
        - arm_left/shoulder_rotation
        - arm_left/shoulder_flexion

  gravity_compensation_controller:
    ros__parameters:
      joints:
        - arm_left/shoulder_rotation
        - arm_left/shoulder_flexion
```

Controller entries under `controller_manager.ros__parameters` support:

- `type`: Required controller plugin type.
- `state`: Optional startup state metadata. Use `active` or `inactive`; default is `active`.
- `remappings`: Optional dictionary of controller topic remappings.

Example remapping:

```yaml
/**:
  controller_manager:
    ros__parameters:
      mecanum_drive_controller:
        type: mecanum_drive_controller/MecanumDriveController
        state: active
        remappings:
          mecanum_drive_controller/reference: cmd_vel
```

`state` and `remappings` are consumed by `control.launch.py` and are not uploaded as ROS parameters. All controllers are spawned with `--inactive`; controllers marked `active` are activated later by `controller_activator_node.py`.

## Hardware Activation

Hardware components can be listed as initially inactive:

```yaml
/**:
  controller_manager:
    ros__parameters:
      hardware_components_initial_state:
        inactive:
          - DuaTorsoSystem
```

When this list is present, `hardware_activator_node.py` runs after all controller spawners finish and before controller activation. It calls the controller manager services to transition each listed component to `active`, configuring an `unconfigured` component first if needed.

If no inactive hardware components are configured, hardware activation is skipped.

## Gazebo Sim URDF Plugin

Include the xacro macro in the robot description:

```xml
<xacro:include filename="$(find duatic_control)/urdf/plugins.urdf.xacro" />
<xacro:control namespace="$(arg namespace)" />
```

The macro adds the `gz_ros2_control::GazeboSimROS2ControlPlugin`, sets the namespace, and remaps common global topics into the namespace. The plugin loads the packaged `config/controller_manager.yaml`; controller-specific configuration is still provided through `control.launch.py config_path:=...`.

## Troubleshooting

- If no controllers load, validate the YAML syntax and confirm `/**/controller_manager/ros__parameters` exists.
- If the launch fails immediately, check that `config_path` points to an existing YAML file.
- If a controller fails to activate, confirm its required hardware component was listed under `hardware_components_initial_state.inactive` when it should start inactive.
- If Gazebo Sim already provides the controller manager, launch with `use_sim_time:=true` so `ros2_control_node` is not started twice.
