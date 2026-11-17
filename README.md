# Duatic Control
[![Jazzy](https://github.com/Duatic/duatic_control/raw/badges/jazzy.svg)](https://github.com/Duatic/duatic_control/actions/workflows/ci.yml)
[![Kilted](https://github.com/Duatic/duatic_control/raw/badges/kilted.svg)](https://github.com/Duatic/duatic_control/actions/workflows/ci.yml)
[![Lyrical](https://github.com/Duatic/duatic_control/raw/badges/lyrical.svg)](https://github.com/Duatic/duatic_control/actions/workflows/ci.yml)
[![Rolling](https://github.com/Duatic/duatic_control/raw/badges/rolling.svg)](https://github.com/Duatic/duatic_control/actions/workflows/ci.yml)

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

## Staged bringup
A bringup launch file can start its parts in stages. A stage is a group of launch actions plus a gate, a process that exits 0 once the stage is up. A stage starts when every stage it comes `after` is ready.

```python
from launch.actions import GroupAction
from launch_ros.actions import PushRosNamespace
from duatic_control.core import core_stage
from duatic_control.stages import Stage, gate, stage_arguments, staged

stages = [
    core_stage(robot_description, controllers_config, namespace="robot1"),
    Stage("imu", [imu_driver], gate("imu", 30, topics=["sensor/imu/data"])),
    Stage("state_estimation", [ekf], gate("state_estimation", 30, topics=["odometry/filtered"]), after=["core", "imu"]),
]
return [
    *stage_arguments(["imu", "state_estimation"]),
    GroupAction([PushRosNamespace("robot1"), staged(stages)]),
]
```

- `core_stage` starts the robot state publisher, the controller manager, the controllers through `control.launch.py`, brake release and the e-stop node. Pass the same `namespace` as the surrounding `PushRosNamespace`, because the controllers are spawned outside its scope. It is ready once every controller in the config is in its configured state and every hardware component is active. If the controller manager exits, the launch shuts down.
- `gate` checks any combination of: a first message on `topics`, the controllers in `controllers_config`, active hardware components, and active `lifecycle_nodes`. After `timeout` seconds it logs every check that has not passed and exits 1. Timeouts run on wall time, also under `use_sim_time`. The `stage_timeout_scale` argument multiplies every gate timeout, for example `stage_timeout_scale:=5` for a slow simulator start.
- A gate only checks the start of its stage. Nothing watches a stage once it is ready, except that the launch shuts down if the controller manager exits. Switching controllers before the core stage is ready, for example with the e-stop, fails the core stage.
- Every configurable stage has a `require_<stage>` argument, `true` by default. If a required stage fails, the launch shuts down with the reason. If it is set to `false`, the launch continues without the stage and skips the stages that come after it. A skipped stage that is itself required still shuts the launch down. The core stage is always required.
- Declare the `require_<stage>` and `stage_timeout_scale` arguments with `stage_arguments` in `generate_launch_description`, so that `ros2 launch <package> <file> --show-args` lists them.
- Place `staged(...)` where the stages should take their namespace, launch arguments and environment from, for example after `PushRosNamespace` in a `GroupAction`. Each stage runs in its own scope, so launch configurations set by one stage are not seen by the others.
- A launch file started by a stage can run its own `staged(...)`. Those stages are not part of the outer graph: stages that come after the outer stage do not wait for them. Stage names must be unique across all graphs in one namespace, because each gate node is named `<stage>_gate`.
- Stage names may contain letters, digits and underscores, and start with a letter.

## Troubleshooting
- If controllers don't load: validate YAML syntax, ensure `/**:` is present, and confirm the launch passes an absolute path to the controllers file.
