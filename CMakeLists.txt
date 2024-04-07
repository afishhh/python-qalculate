cmake_minimum_required(VERSION 3.18...3.22)
project(
	python-qalculate
	LANGUAGES CXX
	VERSION 0.0.1
)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/BuildWheel.cmake")

find_package(
	Python 3.6
	COMPONENTS Interpreter Development.Module
	REQUIRED
)
find_package(pybind11 CONFIG REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBQALCULATE REQUIRED libqalculate)

file(GLOB GENERATOR_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/generate/*.py")
set(GENERATED_SOURCE_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")

set(REGENERATE OFF)
foreach(SOURCE_FILE ${GENERATOR_SOURCES})
	if("${SOURCE_FILE}" IS_NEWER_THAN "${CMAKE_CURRENT_BINARY_DIR}/generated-timestamp")
		set(REGENERATE ON)
		break()
	endif()
endforeach()

if(${REGENERATE})
	execute_process(
		COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/generate.sh" "${CMAKE_CURRENT_BINARY_DIR}/libqalculate-src" "${GENERATED_SOURCE_DIR}"
		WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
		COMMAND_ERROR_IS_FATAL ANY
	)
	file(TOUCH "${CMAKE_CURRENT_BINARY_DIR}/generated-timestamp")
endif()

file(GLOB SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cc" "${GENERATED_SOURCE_DIR}/*.cc")

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
	"${GENERATED_SOURCE_DIR}"
)

set_target_properties(
	python-qalculate
	PROPERTIES
	OUTPUT_NAME qalculate
)

add_custom_command(
	TARGET python-qalculate
	POST_BUILD
	COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/generate_stubs.sh" "${CMAKE_CURRENT_BINARY_DIR}"
	BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/qalculate.pyi"
	VERBATIM
)

build_binary_wheel(
	TARGET python-qalculate
	STUBS "${CMAKE_CURRENT_BINARY_DIR}/qalculate.pyi"
)
