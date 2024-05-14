#pragma once

#include <libqalculate/MathStructure.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>

namespace PYBIND11_NAMESPACE {
template <> struct polymorphic_type_hook<MathStructure> {
  static void const *get(MathStructure const *src, std::type_info const *&type);
};
} // namespace PYBIND11_NAMESPACE

namespace py = pybind11;
