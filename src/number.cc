#include "number.hh"

Number number_from_python_int(py::int_ value) {
  int overflow;
  long long long_value = PyLong_AsLongLongAndOverflow(value.ptr(), &overflow);
  if (overflow != 0) {
    py::int_ positive;
    if (overflow < 0) {
      PyObject *result = PyNumber_Absolute(value.ptr());
      if (result == nullptr)
        throw py::error_already_set();
      positive = pybind11::reinterpret_steal<py::int_>(result);
    } else
      positive = value;

    auto bytes = positive.attr("to_bytes")(512).cast<py::bytes>();
    auto result = Number();

    for (auto byte : bytes) {
      result.multiply(256);
      result.add(byte.cast<long>());
    }

    if (overflow < 0)
      result.negate();

    return result;
  } else if (PyErr_Occurred())
    throw py::error_already_set();
  else
    return long_value;
}

Number number_from_complex(std::complex<long double> complex) {
  Number result(complex.real());
  result.setImaginaryPart(complex.imag());
  return result;
}

py::int_ assert_and_steal_int(PyObject *object) {
  assert(object != nullptr);
  return py::reinterpret_steal<py::int_>(object);
}

#ifdef NDEBUG
#define assert_kept(expr) expr
#else
#define assert_kept(expr) assert(expr)
#endif

py::int_ number_to_python_int(Number const &number) {
  if (!number.isInteger())
    throw py::value_error("Non-integer Number cannot be converted into an int");

  {
    bool overflowed = false;
    long value = number.lintValue(&overflowed);
    if (!overflowed)
      return assert_and_steal_int(PyLong_FromLong(value));
  }

  constexpr long int bits = std::numeric_limits<long int>::digits - 1;
  constexpr long int mask = ((long int)1 << bits) - 1;
  std::vector<long int> limbs;

  Number current = number;
  if (current.isNegative())
    assert_kept(current.negate());

  while (current.isNonZero()) {
    Number tmp = current;
    assert_kept(tmp.bitAnd(mask));
    limbs.push_back(tmp.ulintValue());
    assert_kept(current.shiftRight(bits));
  }

  py::int_ pybits = assert_and_steal_int(PyLong_FromLong(bits));
  py::int_ pymask = assert_and_steal_int(PyLong_FromLong(mask));
  py::int_ result = assert_and_steal_int(PyLong_FromLong(limbs.back()));
  limbs.pop_back();

  while (!limbs.empty()) {
    result = assert_and_steal_int(
        PyNumber_InPlaceLshift(result.ptr(), pybits.ptr()));
    py::int_ limb = assert_and_steal_int(PyLong_FromLong(limbs.back()));
    result =
        assert_and_steal_int(PyNumber_InPlaceAdd(result.ptr(), limb.ptr()));
    limbs.pop_back();
  }

  if (number.isNegative())
    result = assert_and_steal_int(PyNumber_Negative(result.ptr()));

  return result;
}

py::float_ number_to_python_float(Number const &number) {
  if (!number.isFloatingPoint())
    throw py::value_error{};
  return number.floatValue();
}

py::object number_to_python_complex(Number const &number) {
  if (!number.isComplex() || !number.isFloatingPoint() ||
      !number.imaginaryPart().isFloatingPoint())
    throw py::value_error{};
  return py::cast(
      std::complex(number.floatValue(), number.imaginaryPart().floatValue()));
}
