cmake_minimum_required(VERSION 3.18...3.22)
project(python-qalculate LANGUAGES CXX)

find_package(
	Python 3.6
	COMPONENTS Interpreter Development.Module
	REQUIRED
)
find_package(pybind11 CONFIG REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBQALCULATE REQUIRED libqalculate)

execute_process(
	COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/generate.sh" "${CMAKE_CURRENT_BINARY_DIR}/libqalculate-src" "${CMAKE_CURRENT_BINARY_DIR}/generated"
	WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
	COMMAND_ERROR_IS_FATAL ANY
)

file(GLOB SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cc" "${CMAKE_CURRENT_BINARY_DIR}/generated/*.cc")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

pybind11_add_module(
	python-qalculate
	${SOURCES}
)

target_link_libraries(
	python-qalculate
	PRIVATE
	"${LIBQALCULATE_LIBRARIES}"
)

target_include_directories(
	python-qalculate
	PRIVATE
	"${CMAKE_CURRENT_SOURCE_DIR}/src"
	"${CMAKE_CURRENT_BINARY_DIR}/generated"
)

set_target_properties(
	python-qalculate
	PROPERTIES
	OUTPUT_NAME qalculate
)

add_custom_command(
	TARGET python-qalculate
	POST_BUILD
	COMMAND "cp" "qalculate.cpython-311-x86_64-linux-gnu.so" /tmp
	BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/qalculate.pyi"
)

add_custom_command(
	TARGET python-qalculate
	POST_BUILD
	COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/generate_stubs.sh" "${CMAKE_CURRENT_BINARY_DIR}"
	BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/qalculate.pyi"
)
