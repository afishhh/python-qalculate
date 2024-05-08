#pragma once

#include "pybind.hh"
#include <cassert>
#include <complex>
#include <concepts>
#include <libqalculate/MathStructure.h>
#include <libqalculate/qalculate.h>
#include <pybind11/cast.h>
#include <pybind11/complex.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <string_view>
#include <type_traits>

#include "number.hh"
#include "ref.hh"

// FIXME: split up generated.hh into separate files
void MathStructure_repr(MathStructure const *mstruct, std::string &output);

inline PrintOptions repr_print_options;

template <typename Child, typename TBase = MathStructure>
class MathStructureProxy : public TBase {
  static_assert(std::is_base_of_v<MathStructure, TBase>);

protected:
  template <typename... Args>
  MathStructureProxy(Args &&...args) : TBase(std::forward<Args>(args)...) {
    this->i_ref = 0;
  }

public:
  using Base = TBase;

  static void init(qalc_class_<Child, TBase> &c) {
    c.def(py::init([](Child const &self) { return self; }));
    Child::_init(c);
  }
};

template <typename... Extra>
constexpr bool has_any_arg_extra = (std::is_base_of_v<py::arg, Extra> || ...);

template <typename... Args, typename C, typename... Extra>
auto static_new(C &c, Extra &&...extra) {
  using T = typename C::type;
  auto fun = [](py::type type, Args... args) {
    auto expected_type = py::type::of<T>();
    if (!type.is(expected_type))
      throw py::type_error("cls must be " +
                           py::str(expected_type).template cast<std::string>());
    return T(args...);
  };

  if constexpr (has_any_arg_extra<Extra...>)
    c.def_static("__new__", fun, py::arg("cls"), std::forward<Extra>(extra)...);
  else
    c.def_static("__new__", fun, std::forward<Extra>(extra)...);
}

#define PROXY_CHILD_ACCESSOR(name, index)                                      \
  def_property(                                                                \
      name, [](MathStructure const &self) { return self[index]; },             \
      [](MathStructure const &self) { return self[index]; })

template <typename Arg>
void _math_structure_append_child(MathStructure &out, Arg &&child) {
  child->ref();
  out.addChild_nocopy((MathStructure *)child);
}

#define PROXY_APPEND_CHILD(child)                                              \
  do {                                                                         \
    child->ref();                                                              \
    this->addChild_nocopy(child);                                              \
  } while (0)

#define PROXY_APPEND_CHILD_OPT(child, default)                                 \
  if (child)                                                                   \
    PROXY_APPEND_CHILD(child);                                                 \
  else                                                                         \
    PROXY_APPEND_CHILD(default);

class MathStructureSequence : public MathStructureProxy<MathStructureSequence> {
public:
  void del_item(size_t idx) {
    idx += 1;
    if (idx > this->size() || idx == 0)
      throw py::index_error{};
    this->delChild(idx);
  }

  void append(MathStructure *other) {
    other->ref();
    this->addChild_nocopy(other);
  }
};

inline MathStructure const &
math_structure_getitem_idx(MathStructure const &self, size_t idx) {
  if (idx >= self.size())
    throw py::index_error();
  return self[idx];
}

inline py::list math_structure_getitem_slice(MathStructure const &self,
                                             py::slice slice) {
  auto wrap_index = [self](ssize_t x) -> size_t {
    if (x < 0)
      return self.size() + -(-x % self.size());
    return x;
  };

  auto start = wrap_index(slice.attr("start").cast<ssize_t>());
  auto stop = wrap_index(slice.attr("stop").cast<ssize_t>());
  ssize_t step = 1;
  if (auto step_obj = slice.attr("step"); !step_obj.is_none())
    step = step_obj.cast<ssize_t>();
  bool reverse = stop < start;

  if (reverse && step > 0)
    return py::list{};
  else if (!reverse && step < -1)
    return py::list{};
  else if (step == 0)
    throw py::value_error("slice step cannot be zero");

  if (start >= self.size() || stop >= self.size())
    throw py::index_error{};

  py::list result;
  for (ssize_t i = start; reverse ? i > (ssize_t)stop : i < (ssize_t)stop;
       i += step)
    result.append(&self[i]);
  return result;
}

inline qalc_class_<MathStructure> &
init_math_structure_children(py::module_ &,
                             qalc_class_<MathStructure> &mstruct) {
  qalc_class_<MathStructureSequence, MathStructure>(mstruct, "Sequence")
      .def("append", &MathStructureSequence::append, py::is_operator{})
      .def("__delitem__", &MathStructureSequence::del_item, py::is_operator{});

  return mstruct
      .def("__getitem__", &math_structure_getitem_idx,
           py::return_value_policy::reference_internal)
      .def("__getitem__", &math_structure_getitem_slice,
           py::return_value_policy::reference_internal)

      .def(
          "__len__", [](MathStructure const &self) { return self.size(); },
          py::is_operator{})

      .def(
          "__repr__",
          [](MathStructure const *self) {
            std::string output;
            MathStructure_repr(self, output);
            return output;
          },
          py::is_operator{});
}

class MathStructureNumberProxy final
    : public MathStructureProxy<MathStructureNumberProxy> {
public:
  MathStructureNumberProxy() {}
  MathStructureNumberProxy(py::int_ value)
      : MathStructureProxy(number_from_python_int(value)) {}
  MathStructureNumberProxy(double value) : MathStructureProxy(Number(value)) {}
  MathStructureNumberProxy(std::complex<double> value)
      : MathStructureProxy(number_from_complex(value)) {}
  MathStructureNumberProxy(Number const &number) : MathStructureProxy(number) {}

  static void _init(qalc_class_<MathStructureNumberProxy, Base> &c) {
    static_new<>(c);
    static_new<Number>(c);
    static_new<py::int_>(c);
    static_new<double>(c);
    static_new<std::complex<double>>(c);
    c.def_property("value",
                   (Number & (MathStructure ::*)()) & MathStructure::number,
                   [](MathStructureNumberProxy &self, Number const &value) {
                     self.o_number.set(value);
                   })

        .def("__int__",
             [](MathStructureNumberProxy &self) {
               return number_to_python_int(self.o_number);
             })

        .def("__float__",
             [](MathStructureNumberProxy &self) {
               return number_to_python_float(self.o_number);
             })

        .def("__complex__",
             [](MathStructureNumberProxy &self) {
               return number_to_python_complex(self.o_number);
             })

        .def(
            "__repr__",
            [](MathStructure const &self) {
              return self.number().print(repr_print_options);
            },
            py::is_operator{});
    py::implicitly_convertible<py::int_, MathStructureNumberProxy>();
    py::implicitly_convertible<double, MathStructureNumberProxy>();
    py::implicitly_convertible<std::complex<double>,
                               MathStructureNumberProxy>();
  }

  void repr(std::string &output) const {
    output += "MathStructure.Number(";
    output += this->number().print(repr_print_options);
    output += ")";
  }
};

template <typename Self>
class MathStructureGenericOperationProxy
    : public MathStructureProxy<Self, MathStructureSequence> {
public:
  MathStructureGenericOperationProxy() { this->m_type = Self::TYPE; }

  MathStructureGenericOperationProxy(py::sequence args)
      : MathStructureGenericOperationProxy() {
    for (auto value : args) {
      auto structure = value.cast<MathStructureRef>();
      PROXY_APPEND_CHILD(structure);
    }
  }

  static void _init(qalc_class_<Self, MathStructureSequence> &c) {
    static_new<py::sequence>(c);
  }

  void repr(std::string &output) const {
    output += Self::PYTHON_NAME;
    output += "([";
    for (size_t i = 0; i < this->size(); ++i) {
      if (i != 0)
        output += ", ";
      MathStructure_repr(&(*this)[i], output);
    }
    output += "])";
  }
};

#define GENERIC_OPERATION_PROXY1(proxy, type, name)                            \
  class proxy final : public MathStructureGenericOperationProxy<proxy> {       \
  public:                                                                      \
    proxy(py::args args) : MathStructureGenericOperationProxy(args) {}         \
    static constexpr std::string_view PYTHON_NAME = name;                      \
    static constexpr StructureType TYPE = type;                                \
  }

#define GENERIC_OPERATION_PROXY(name, type)                                    \
  GENERIC_OPERATION_PROXY1(MathStructure##name##Proxy, type,                   \
                           "MathStructure." #name)

#define STUB_PROXY(name)                                                       \
  class MathStructure##name##Proxy final : public MathStructure {              \
  public:                                                                      \
    using Base = MathStructure;                                                \
    static void init(qalc_class_<MathStructure##name##Proxy, Base> &c) {       \
      c.def_static("__new__",                                                  \
                   []() { throw py::type_error("unimplemented"); });           \
    }                                                                          \
    void repr(std::string &output) const {                                     \
      output += "<MathStructure." #name ">";                                   \
    }                                                                          \
  }

GENERIC_OPERATION_PROXY(Multiplication, STRUCT_MULTIPLICATION);
GENERIC_OPERATION_PROXY(Addition, STRUCT_ADDITION);

GENERIC_OPERATION_PROXY(BitwiseAnd, STRUCT_BITWISE_AND);
GENERIC_OPERATION_PROXY(BitwiseOr, STRUCT_BITWISE_OR);
GENERIC_OPERATION_PROXY(BitwiseXor, STRUCT_BITWISE_XOR);
GENERIC_OPERATION_PROXY(BitwiseNot, STRUCT_BITWISE_NOT);

GENERIC_OPERATION_PROXY(LogicalAnd, STRUCT_LOGICAL_AND);
GENERIC_OPERATION_PROXY(LogicalOr, STRUCT_LOGICAL_OR);
GENERIC_OPERATION_PROXY(LogicalXor, STRUCT_LOGICAL_XOR);
GENERIC_OPERATION_PROXY(LogicalNot, STRUCT_LOGICAL_NOT);

class MathStructureComparisonProxy final
    : public MathStructureProxy<MathStructureComparisonProxy> {
public:
  MathStructureComparisonProxy(MathStructure *left, ComparisonType type,
                               MathStructure *right) {
    setType(STRUCT_COMPARISON);
    setComparisonType(type);
    PROXY_APPEND_CHILD_OPT(left, MathStructureRef::construct(0));
    PROXY_APPEND_CHILD_OPT(right, MathStructureRef::construct(0));
  }
  MathStructureComparisonProxy()
      : MathStructureComparisonProxy(nullptr, COMPARISON_EQUALS, nullptr) {}

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructureComparisonProxy, Base> &c) {
    static_new<MathStructure *, ComparisonType, MathStructure *>(
        c, py::arg("left") = static_cast<MathStructure *>(nullptr),
        py::arg("type") = ComparisonType::COMPARISON_EQUALS,
        py::arg("right") = static_cast<MathStructure *>(nullptr));
    c.PROXY_CHILD_ACCESSOR("left", 0)
        .PROXY_CHILD_ACCESSOR("right", 1)
        .def_property("type", &MathStructure::comparisonType,
                      &MathStructure::setComparisonType);
  }

  void repr(std::string &output) const {
    output += "MathStructure.Comparison(left=";
    MathStructure_repr(&(*this)[0], output);
    output += ", type=";
    output += ((py::object)py::cast(this->comparisonType()))
                  .attr("__repr__")()
                  .cast<std::string>();
    output += ", right=";
    MathStructure_repr(&(*this)[1], output);
    output += ")";
  }
};

STUB_PROXY(Datetime);

class MathStructureVariableProxy final
    : public MathStructureProxy<MathStructureVariableProxy> {
public:
  MathStructureVariableProxy() { setType(STRUCT_VARIABLE); }
  MathStructureVariableProxy(QalcRef<Variable> variable)
      : MathStructureVariableProxy() {
    setVariable(variable.forget());
  }

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructureVariableProxy, Base> &c) {
    static_new<QalcRef<Variable>>(c);
    c.def_property("variable", &MathStructure::variable,
                   &MathStructure::setVariable);
  }

  void repr(std ::string &output) const {
    output += "MathStructure.Variable(variable=";
    output +=
        py::cast(this->variable()).attr("__repr__")().cast<std::string_view>();
    output += ")";
  }
};

class MathStructureFunctionProxy final
    : public MathStructureProxy<MathStructureFunctionProxy> {
public:
  MathStructureFunctionProxy() { setType(STRUCT_FUNCTION); }

  MathStructureFunctionProxy(QalcRef<MathFunction> function)
      : MathStructureFunctionProxy() {
    setFunction(function.forget());
  }

  MathStructureFunctionProxy(QalcRef<MathFunction> function, py::args args)
      : MathStructureFunctionProxy(function) {
    for (auto arg : args) {
      auto *marg = arg.cast<MathStructure *>();
      marg->ref();
      addChild_nocopy(marg);
    }
  }

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructureFunctionProxy, Base> &c) {
    static_new<QalcRef<MathFunction>, py::args>(c, py::arg("function"),
                                                py::pos_only{});
    c.def_property_readonly("function",
                            [](MathStructureFunctionProxy const &self) {
                              return QalcRef(self.o_function);
                            });
  }

  void repr(std::string &output) const {
    output += "MathStructure.Function(function=";
    output += ((py::object)py::cast(this->function()))
                  .attr("__repr__")()
                  .cast<std::string>();
    output += ", args=[";
    for (size_t i = 0; i < this->countChildren(); ++i) {
      if (i != 0)
        output += ", ";
      output += py::cast(&(*this)[i]).attr("__repr__")().cast<std::string>();
    }
    output += "])";
  }
};

STUB_PROXY(Symbolic);

class MathStructureUnitProxy final
    : public MathStructureProxy<MathStructureUnitProxy> {
public:
  MathStructureUnitProxy() { setType(STRUCT_UNIT); }
  MathStructureUnitProxy(Unit *unit) : MathStructureUnitProxy() {
    setUnit(unit);
  }

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructureUnitProxy, Base> &c) {
    static_new<Unit *>(c, py::arg("unit"));
    c.def_property_readonly("unit", [](MathStructureUnitProxy const &self) {
      return QalcRef(self.o_unit);
    });
  }

  void repr(std::string &output) const {
    output += "MathStructure.Unit(unit=";
    output +=
        py::cast(this->unit()).attr("__repr__")().cast<std::string_view>();
    output += ")";
  }
};

class MathStructurePowerProxy final
    : public MathStructureProxy<MathStructurePowerProxy> {
public:
  MathStructurePowerProxy(MathStructure *base, MathStructure *exponent) {
    setType(STRUCT_POWER);
    PROXY_APPEND_CHILD_OPT(base, MathStructureRef::construct(0));
    PROXY_APPEND_CHILD_OPT(exponent, MathStructureRef::construct(0));
  }
  MathStructurePowerProxy() : MathStructurePowerProxy(nullptr, nullptr) {}

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructurePowerProxy, Base> &c) {
    static_new<MathStructure *, MathStructure *>(
        c, py::arg("base") = static_cast<MathStructure *>(nullptr),
        py::arg("exponent") = static_cast<MathStructure *>(nullptr));
    c.PROXY_CHILD_ACCESSOR("base", 0).PROXY_CHILD_ACCESSOR("exponent", 1);
  }

  void repr(std::string &output) const {
    output += "MathStructure.Power(base=";
    MathStructure_repr(this->base(), output);
    output += ", exponent=";
    MathStructure_repr(this->exponent(), output);
    output += ")";
  }
};

STUB_PROXY(Negate);
STUB_PROXY(Inverse);

class MathStructureVectorProxy
    : public MathStructureProxy<MathStructureVectorProxy,
                                MathStructureSequence> {
public:
  MathStructureVectorProxy() { setType(STRUCT_VECTOR); }
  MathStructureVectorProxy(py::sequence items) : MathStructureVectorProxy() {
    for (auto item : items)
      _math_structure_append_child(*this, item.cast<MathStructureRef>());
  }

  using Base = MathStructureSequence;

  static void _init(qalc_class_<MathStructureVectorProxy, Base> &c) {
    static_new<>(c);
    static_new<py::list>(c);
    c.def_property_readonly("rows", &MathStructure::rows)
        .def_property_readonly("columns", &MathStructure::columns)
        .def("__getitem__", &math_structure_getitem_idx,
             py::return_value_policy::reference_internal)
        .def("__getitem__", &math_structure_getitem_slice,
             py::return_value_policy::reference_internal)
        .def(
            "__getitem__",
            [](MathStructure &self, std::tuple<size_t, size_t> xy) {
              auto [x, y] = xy;
              return self.getElement(x, y);
            },
            py::is_operator{}, py::return_value_policy::reference_internal)
        .def("flatten",
             [](MathStructure &self) {
               auto result = MathStructureRef::construct();
               self.flattenVector(*result);
               return result;
             })
        .def(
            "rank",
            [](MathStructure &self, bool ascending) {
              auto result = MathStructureRef::construct(self);
              result->rankVector(ascending);
              return result;
            },
            py::arg("ascending") = true)
        .def(
            "sort",
            [](MathStructure &self, bool ascending) {
              auto result = MathStructureRef::construct(self);
              result->sortVector(ascending);
              return result;
            },
            py::arg("ascending") = true)
        .def("flip", [](MathStructure &self) {
          auto result = MathStructureRef::construct(self);
          self.flipVector();
          return result;
        });
    py::implicitly_convertible<py::sequence, MathStructureVectorProxy>();
  }

  void repr(std::string &output) const {
    output += "MathStructure.Vector([";
    for (size_t i = 0; i < size(); ++i) {
      if (i)
        output += ", ";
      MathStructure_repr(&(*this)[i], output);
    }
    output += "])";
  }
};

class MathStructureUndefinedProxy
    : public MathStructureProxy<MathStructureUndefinedProxy> {
public:
  MathStructureUndefinedProxy() { setType(STRUCT_UNDEFINED); }

  using Base = MathStructure;

  static void _init(qalc_class_<MathStructureUndefinedProxy, Base> &c) {
    static_new<>(c);
  }

  void repr(std::string &output) const {
    output += "MathStructure.Undefined()";
  }
};

STUB_PROXY(Division);
