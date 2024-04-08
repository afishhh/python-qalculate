function(build_binary_wheel)
	set(ONE_VALUE_ARGS TARGET STUBS)
	cmake_parse_arguments(
		PARSE_ARGV 0
		ARG
		""
		"${ONE_VALUE_ARGS}"
		""
	)

	if(NOT DEFINED ARG_TARGET)
		message(SEND_ERROR "TARGET argument not provided to build_binary_wheel")
		return()
	endif()

	get_target_property(
		T_NAME
		"${ARG_TARGET}"
		OUTPUT_NAME
	)

	if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
		set(T_SYSTEM "linux")
	else()
		message(SEND_ERROR "TODO: System ${CMAKE_SYSTEM_NAME} is not supported in build_binary_wheel yet!")
		return()
	endif()

	set(
		INTERPRETER_NAME "cp${Python_VERSION_MAJOR}${Python_VERSION_MINOR}"
	)

	set(
		WHEEL_TAG "${INTERPRETER_NAME}-${INTERPRETER_NAME}-${T_SYSTEM}_${CMAKE_SYSTEM_PROCESSOR}"
	)

	set(
		WHEEL_FILESTEM "${T_NAME}-${CMAKE_PROJECT_VERSION}-${WHEEL_TAG}"
	)

	set(
		UNPACKED_WHEEL_DIR
		"${CMAKE_CURRENT_BINARY_DIR}/${WHEEL_FILESTEM}"
	)

	file(MAKE_DIRECTORY ${UNPACKED_WHEEL_DIR})

	macro(add_copy_command SOURCE DEST)
		list(APPEND EXTRA_DEPS "${DEST}")
		add_custom_command(
			OUTPUT "${DEST}"
			COMMAND
				"${CMAKE_COMMAND}" -E copy "${SOURCE}" "${DEST}"
			DEPENDS "${SOURCE}"
			VERBATIM
		)
	endmacro()

	set(DISTINFO_DIR "${UNPACKED_WHEEL_DIR}/${T_NAME}-${CMAKE_PROJECT_VERSION}.dist-info")
	set(DATA_DIR "${UNPACKED_WHEEL_DIR}/${T_NAME}")

	if(DEFINED ARG_STUBS)
		file(MAKE_DIRECTORY "${DATA_DIR}")

		file(TOUCH "${DATA_DIR}/py.typed")
		add_copy_command(
			"${ARG_STUBS}"
			"${DATA_DIR}/__init__.pyi"
		)
	endif()

	file(MAKE_DIRECTORY "${DISTINFO_DIR}")

	string(APPEND METADATA "Metadata-Version: 2.1\n")
	string(APPEND METADATA "Name: ${T_NAME}\n")
	string(APPEND METADATA "Version: ${CMAKE_PROJECT_VERSION}\n")
	# TODO: What is our minimum supported version?
	string(APPEND METADATA "Requires-Python: >=3.9\n")
	file(WRITE "${DISTINFO_DIR}/METADATA" "${METADATA}")

	string(APPEND WHEEL "Wheel-Version: 1.0\n")
	string(APPEND WHEEL "Generator: python-qalculate-cmake (${CMAKE_PROJECT_VERSION})\n")
	string(APPEND WHEEL "Root-Is-Purelib: false\n")
	string(APPEND WHEEL "Tag: ${WHEEL_TAG}\n")
	file(WRITE "${DISTINFO_DIR}/WHEEL" "${WHEEL}")

	file(WRITE "${DISTINFO_DIR}/top_level.txt" "${T_NAME}\n")

	set(EXTLIBNAME "${T_NAME}.${Python_SOABI}${CMAKE_SHARED_LIBRARY_SUFFIX}")

	add_copy_command(
		"${CMAKE_CURRENT_BINARY_DIR}/${EXTLIBNAME}"
		"${UNPACKED_WHEEL_DIR}/${EXTLIBNAME}"
	)

	list(APPEND EXTRA_DEPS "${ARG_TARGET}")
	add_custom_command(
		OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/${WHEEL_FILESTEM}.whl"
		COMMAND
		COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/cmake/write_wheel_record.py" "${UNPACKED_WHEEL_DIR}"
		COMMAND
			"${CMAKE_COMMAND}" -E tar
			c "../${WHEEL_FILESTEM}.whl" --format=zip .
		WORKING_DIRECTORY "${UNPACKED_WHEEL_DIR}"
		DEPENDS ${EXTRA_DEPS}
		VERBATIM
	)

	add_custom_target(
		"${ARG_TARGET}-wheel" ALL
		DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/${WHEEL_FILESTEM}.whl"
	)
endfunction()
