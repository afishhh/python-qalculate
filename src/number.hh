#pragma once

#include "pybind.hh"

#include <complex>
#include <pybind11/pytypes.h>

Number number_from_python_int(py::int_ value);
Number number_from_complex(std::complex<double> complex);
py::int_ number_to_python_int(Number const &number);
py::float_ number_to_python_float(Number const &number);
py::object number_to_python_complex(Number const &number);
