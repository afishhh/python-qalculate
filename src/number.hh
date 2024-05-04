#pragma once

#include "pybind.hh"

#include <complex>

Number number_from_python_int(py::int_ value);
Number number_from_complex(std::complex<long double> complex);
py::int_ number_to_python_int(Number const &number);
