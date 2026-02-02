import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGUMENTS = [
    DeclareLaunchArgument(
        "config_path", default_value="", description="Path to the controller config YAML file."
    ),
    DeclareLaunchArgument("namespace", default_value=""),
]


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

    # Spawn controllers
    nodes = []
    for controller_name, state, remappings in controllers:
        args = [
            controller_name,
            "-c",
            "controller_manager",
            "--switch-timeout",
            "30.0",
            "--param-file",
            config_path,
        ]
        # Add --inactive if controller should start inactive
        if state == "inactive":
            args.append("--inactive")

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
        nodes.append(node)

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

    spawn_controller_after_loading_params = RegisterEventHandler(
        OnProcessExit(
            target_action=load_params, on_exit=nodes  # Spawn controllers after params loaded
        )
    )

    return [load_params, spawn_controller_after_loading_params]


def generate_launch_description():
    # Define LaunchDescription variable
    ld = LaunchDescription(ARGUMENTS)

    # Add nodes to LaunchDescription
    ld.add_action(OpaqueFunction(function=launch_setup))
    return ld
