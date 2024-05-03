set(
	LIBQALCULATE_SOURCE_PATH  "$ENV{LIBQALCULATE_SOURCE_PATH}"
	CACHE STRING "The libqalculate source path to use for generating bindings."
)
set(
	USE_SYSTEM_LIBQALCULATE ON
	CACHE BOOL "Whether to use libqalculate from pkg-config or build it separately."
)

if(USE_SYSTEM_LIBQALCULATE)
	find_package(PkgConfig REQUIRED)
	pkg_check_modules(LIBQALCULATE REQUIRED libqalculate)

	if(NOT LIBQALCULATE_FOUND)
		message(
			FATAL_ERROR
			"libqalculate not found via pkg-config"
			"Set USE_SYSTEM_LIBQALCULATE to OFF or install libqalculate"
		)
	endif()

	set(LIBQALCULATE_CLONE_REF "v${LIBQALCULATE_VERSION}")
else()
	# TODO: Once fixes for the bugs I found are in a release set this to a proper
	#				version in CMakeLists.txt
	set(LIBQALCULATE_CLONE_REF "master")
endif()

if(LIBQALCULATE_SOURCE_PATH)
	if(NOT IS_ABSOLUTE "${LIBQALCULATE_SOURCE_PATH}")
		message(FATAL_ERROR "LIBQALCULATE_SOURCE_PATH is not an absolute path")
	elseif(NOT EXISTS "${LIBQALCULATE_SOURCE_PATH}")
		message(FATAL_ERROR "LIBQALCULATE_SOURCE_PATH does not exist")
	endif()
	set(LIBQALCULATE_RESOLVED_PATH "${LIBQALCULATE_SOURCE_PATH}")
else()
	set(LIBQALCULATE_CLONE_PATH "${CMAKE_CURRENT_BINARY_DIR}/libqalculate-src")
	if(NOT EXISTS "${LIBQALCULATE_CLONE_PATH}")
		find_package(Git)
		if(NOT "${GIT_FOUND}")
			message(
				FATAL_ERROR
				"LIBQALCULATE_SOURCE_PATH not set and git not found\n"
				"Install git or set an explicit path to qalculate sources"
			)
		endif()
		execute_process(
			COMMAND
				"${GIT_EXECUTABLE}" "clone" "-b" "${LIBQALCULATE_CLONE_REF}" "--depth"
				"1" "https://github.com/Qalculate/libqalculate.git"
				"${LIBQALCULATE_CLONE_PATH}"
			COMMAND_ERROR_IS_FATAL ANY
		)
	endif()
	set(LIBQALCULATE_RESOLVED_PATH "${LIBQALCULATE_CLONE_PATH}")
endif()

if(NOT USE_SYSTEM_LIBQALCULATE)
	cmake_path(
		IS_PREFIX
		CMAKE_CURRENT_BINARY_DIR "${LIBQALCULATE_RESOLVED_PATH}"
		NORMALIZE LIBQALCULATE_IS_IN_BINARY_DIR
	)

	if(LIBQALCULATE_IS_IN_BINARY_DIR)
		set(LIBQALCULATE_BUILD_DIR "${LIBQALCULATE_RESOLVED_PATH}")
	else()
		set(LIBQALCULATE_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/libqalculate-build")
		if(NOT EXISTS "${LIBQALCULATE_BUILD_DIR}")
			execute_process(
				COMMAND
					"${CMAKE_COMMAND}" -E copy_directory_if_different
					"${LIBQALCULATE_RESOLVED_PATH}" "${LIBQALCULATE_BUILD_DIR}"
				COMMAND_ERROR_IS_FATAL ANY
			)
		endif()
	endif()

	add_custom_command(
		OUTPUT "${LIBQALCULATE_BUILD_DIR}/Makefile"
		COMMAND
			"${LIBQALCULATE_BUILD_DIR}/autogen.sh"
			--disable-textport
		WORKING_DIRECTORY "${LIBQALCULATE_BUILD_DIR}"
		VERBATIM
	)

	set(LIBQALCULATE_SO "${LIBQALCULATE_BUILD_DIR}/libqalculate/.libs/libqalculate.so")

	add_custom_command(
		OUTPUT "${LIBQALCULATE_SO}"
		COMMAND make
		WORKING_DIRECTORY "${LIBQALCULATE_BUILD_DIR}"
		DEPENDS "${LIBQALCULATE_BUILD_DIR}/Makefile"
		VERBATIM
	)

	add_custom_target(
		libqalculate_build
		DEPENDS "${LIBQALCULATE_SO}"
	)

	add_library(libqalculate SHARED IMPORTED)
	add_dependencies(libqalculate libqalculate_build)
	set_target_properties(
		libqalculate PROPERTIES
		IMPORTED_LOCATION "${LIBQALCULATE_SO}"
		INTERFACE_INCLUDE_DIRECTORIES "${LIBQALCULATE_BUILD_DIR}/libqalculate"
	)
endif()
