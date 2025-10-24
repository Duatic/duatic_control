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
    DeclareLaunchArgument(
        "namespace", default_value="empty_namespace", description="Robot namespace"
    ),
]


def launch_setup(context, *args, **kwargs):
    namespace = LaunchConfiguration("namespace").perform(context)
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

    # Identify controller names from that section
    controller_names = [
        key for key, value in cm_params.items() if isinstance(value, dict) and "type" in value
    ]
    print(f"Controllers found in YAML: {controller_names}")

    # Spawn controllers
    nodes = []
    for name in controller_names:
        node = Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=[
                name,
                "-c",
                "controller_manager",
                "--switch-timeout",
                "30.0",
                "--param-file",
                config_path,
            ],
            output="screen",
        )
        nodes.append(node)

    # Parameter loader node (runs once and exits)
    load_params = Node(
        package="duatic_control",
        executable="param_loader_node.py",
        name="param_loader",
        output="screen",
        namespace=namespace,
        parameters=[
            {
                "target_node": f"/{namespace}/controller_manager",
                "parameters": yaml.dump(cm_params),  # ✅ send as YAML string
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
