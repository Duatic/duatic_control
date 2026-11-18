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

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY
  config launch urdf
  DESTINATION share/${PROJECT_NAME}/
)

install(
  PROGRAMS
    scripts/param_loader_node.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_extend_controller_config test/test_extend_controller_config.py)
endif()

ament_package()
