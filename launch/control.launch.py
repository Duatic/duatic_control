import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
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
    # Extract controller names from YAML (namespaced format with /**/)
    with open(LaunchConfiguration("config_path").perform(context)) as f:
        data = yaml.safe_load(f)

    # Navigate to the nested parameter section
    # Structure: { "/**": { "ros__parameters": { <controllers>: { ... } } } }
    try:
        params = data["/**"]["controller_manager"]["ros__parameters"]
    except KeyError:
        print("Could not find '/**/ros__parameters' in the YAML file.")
        return []

    # Extract controller names (top-level keys under ros__parameters)
    controller_names = [
        key for key, value in params.items() if isinstance(value, dict) and "type" in value
    ]

    print(f"Controllers found in YAML: {controller_names}")

    # Generate controller spawner nodes
    nodes = []
    for name in controller_names:
        node = Node(
            package="controller_manager",
            executable="spawner",
            namespace=LaunchConfiguration("namespace"),
            arguments=[name, "-c", "controller_manager", "--switch-timeout", "30.0"],
            output="screen",
        )
        nodes.append(node)
    return nodes


def generate_launch_description():
    # Define LaunchDescription variable
    ld = LaunchDescription(ARGUMENTS)

    # Add nodes to LaunchDescription
    ld.add_action(OpaqueFunction(function=launch_setup))
    return ld
