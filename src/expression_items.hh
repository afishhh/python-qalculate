#pragma once

#include <libqalculate/ExpressionItem.h>
#include <libqalculate/Function.h>

#include "pybind.hh"

py::class_<ExpressionName> add_expression_name(py::module_ &m);
qalc_class_<ExpressionItem> add_expression_item(py::module_ &m);
qalc_class_<MathFunction> add_math_function(py::module_ &m);
py::class_<PAssumptions> &add_assumptions(py::module_ &m);
