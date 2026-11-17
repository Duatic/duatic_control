cmake_minimum_required(VERSION 3.22)
project(duatic_control)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

install(DIRECTORY
  config launch urdf
  DESTINATION share/${PROJECT_NAME}/
)

install(
  PROGRAMS
    scripts/param_loader_node.py
    scripts/stage_gate.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_python_install_package(${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(ament_cmake_ros REQUIRED)
  ament_add_pytest_test(test_stages test/test_stages.py TIMEOUT 120)
  # Runs a controller manager, isolated so that it cannot reach other ROS nodes
  ament_add_ros_isolated_pytest_test(test_stage_gate test/test_stage_gate.py TIMEOUT 120)
  ament_add_ros_isolated_pytest_test(test_param_loader test/test_param_loader.py TIMEOUT 180)
endif()

ament_package()
