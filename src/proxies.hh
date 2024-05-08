#pragma once

#include "pybind.hh"
#include <cassert>
#include <complex>
#include <concepts>
#include <libqalculate/MathStructure.h>
#include <libqalculate/qalculate.h>
#include <pybind11/cast.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <string_view>

#include "number.hh"
#include "ref.hh"

// FIXME: split up generated.hh into separate files
void MathStructure_repr(MathStructure const *mstruct, std::string &output);

inline PrintOptions repr_print_options;

// FIXME: how fix
#define PROXY_INIT                                                             \
  do {                                                                         \
    i_ref = 0;                                                                 \
  } while (0)

#define PROXY_CHILD_ACCESSOR(name, index)                                      \
  .def_property(                                                               \
      name, [](MathStructure const &self) { return self[index]; },             \
      [](MathStructure const &self) { return self[index]; })

template <typename Arg>
void _math_structure_append_child(MathStructure &out, Arg &&child) {
  if constexpr (std::is_rvalue_reference_v<Arg>) {
    std::cerr << "forget path\n";
    MathStructure *ptr = child.get();
    child.forget();
    out.addChild_nocopy(ptr);
  } else {
    child->ref();
    out.addChild_nocopy((MathStructure *)child);
  };
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

class MathStructureSequence : public MathStructure {
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

inline qalc_class_<MathStructure> &
init_math_structure_children(py::module_ &,
                             qalc_class_<MathStructure> &mstruct) {
  qalc_class_<MathStructureSequence, MathStructure>(mstruct, "Sequence")
      .def("append", &MathStructureSequence::append, py::is_operator{})
      .def("__delitem__", &MathStructureSequence::del_item, py::is_operator{});

  return mstruct
      .def(
          "__getitem__",
          [](MathStructure const &self, size_t idx) {
            if (idx >= self.size())
              throw py::index_error();
            return &self[idx];
          },
          py::is_operator{})
      .def(
          "__getitem__",
          [](MathStructure const &self, py::slice slice) {
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
            for (ssize_t i = start;
                 reverse ? i > (ssize_t)stop : i < (ssize_t)stop; i += step)
              result.append(&self[i]);
            return result;
          },
          py::is_operator{})

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

class MathStructureNumberProxy final : public MathStructure {
public:
  MathStructureNumberProxy() : MathStructure(0) { PROXY_INIT; }
  MathStructureNumberProxy(Number const &number) : MathStructure(number) {
    PROXY_INIT;
  }

  MathStructureNumberProxy(py::int_ value)
      : MathStructureNumberProxy(number_from_python_int(value)) {}
  MathStructureNumberProxy(long double value)
      : MathStructureNumberProxy(Number(value)) {}
  MathStructureNumberProxy(std::complex<long double> value)
      : MathStructureNumberProxy(number_from_complex(value)) {}

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureNumberProxy, Base> &c) {
    c.def(py::init<>())
        .def(py::init<Number>())
        .def(py::init<py::int_>())
        .def(py::init<long double>())
        .def(py::init<std::complex<long double>>())
        .def_property("value",
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
    py::implicitly_convertible<long double, MathStructureNumberProxy>();
    py::implicitly_convertible<std::complex<long double>,
                               MathStructureNumberProxy>();
  }

  void repr(std::string &output) const {
    output += "MathStructure.Number(";
    output += this->number().print(repr_print_options);
    output += ")";
  }
};

template <size_t MIN_ITEMS, typename Self>
class MathStructureGenericOperationProxy : public MathStructureSequence {
public:
  MathStructureGenericOperationProxy(py::args args) {
    PROXY_INIT;

    if (args.size() < MIN_ITEMS)
      throw py::value_error("At least " + std::to_string(MIN_ITEMS) +
                            " are requried for this node");

    m_type = Self::TYPE;
    for (auto value : args) {
      auto structure = value.cast<MathStructureRef>();
      PROXY_APPEND_CHILD(structure);
    }
  }

  using Base = MathStructureSequence;

protected:
  template <typename T>
  static void init(qalc_class_<T, MathStructureSequence> &c) {
    c.def(py::init<py::args>());
  }

public:
  void repr(std::string &output) const {
    output += Self::PYTHON_NAME;
    output += "([";
    for (size_t i = 0; i < size(); ++i) {
      if (i != 0)
        output += ", ";
      MathStructure_repr(&(*this)[i], output);
    }
    output += "])";
  }
};

#define GENERIC_OPERATION_PROXY1(proxy, type, name, nitems)                    \
  class proxy final                                                            \
      : public MathStructureGenericOperationProxy<nitems, proxy> {             \
  public:                                                                      \
    static constexpr std::string_view PYTHON_NAME = name;                      \
    static constexpr StructureType TYPE = type;                                \
    static void init(qalc_class_<proxy, Base> &c) {                            \
      MathStructureGenericOperationProxy::init(c);                             \
    }                                                                          \
  }

#define GENERIC_OPERATION_PROXY(name, type, nitems)                            \
  GENERIC_OPERATION_PROXY1(MathStructure##name##Proxy, type,                   \
                           "MathStructure." #name, nitems)

#define STUB_PROXY(name)                                                       \
  class MathStructure##name##Proxy final : public MathStructure {              \
  public:                                                                      \
    using Base = MathStructure;                                                \
    static void init(qalc_class_<MathStructure##name##Proxy, Base> &) {}       \
    void repr(std::string &output) const {                                     \
      output += "<MathStructure." #name ">";                                   \
    }                                                                          \
  }

GENERIC_OPERATION_PROXY(Multiplication, STRUCT_MULTIPLICATION, 0);
GENERIC_OPERATION_PROXY(Addition, STRUCT_ADDITION, 0);

GENERIC_OPERATION_PROXY(BitwiseAnd, STRUCT_BITWISE_AND, 0);
GENERIC_OPERATION_PROXY(BitwiseOr, STRUCT_BITWISE_OR, 0);
GENERIC_OPERATION_PROXY(BitwiseXor, STRUCT_BITWISE_XOR, 0);
GENERIC_OPERATION_PROXY(BitwiseNot, STRUCT_BITWISE_NOT, 0);

GENERIC_OPERATION_PROXY(LogicalAnd, STRUCT_LOGICAL_AND, 0);
GENERIC_OPERATION_PROXY(LogicalOr, STRUCT_LOGICAL_OR, 0);
GENERIC_OPERATION_PROXY(LogicalXor, STRUCT_LOGICAL_XOR, 0);
GENERIC_OPERATION_PROXY(LogicalNot, STRUCT_LOGICAL_NOT, 0);

class MathStructureComparisonProxy final : public MathStructure {
public:
  MathStructureComparisonProxy(MathStructure *left, ComparisonType type,
                               MathStructure *right)
      : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_COMPARISON);
    setComparisonType(type);
    PROXY_APPEND_CHILD_OPT(left, MathStructureRef::construct(0));
    PROXY_APPEND_CHILD_OPT(right, MathStructureRef::construct(0));
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureComparisonProxy, Base> &c) {
    c.def(py::init<MathStructure *, ComparisonType, MathStructure *>(),
          py::arg("left") = static_cast<MathStructure *>(nullptr),
          py::arg("type") = ComparisonType::COMPARISON_EQUALS,
          py::arg("right") = static_cast<MathStructure *>(nullptr))
        PROXY_CHILD_ACCESSOR("left", 0) PROXY_CHILD_ACCESSOR("right", 1)
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

class MathStructureVariableProxy final : public MathStructure {
public:
  MathStructureVariableProxy(QalcRef<Variable> variable) {
    PROXY_INIT;
    setType(STRUCT_VARIABLE);
    setVariable(variable.forget());
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureVariableProxy, Base> &class_) {
    class_.def(py::init<QalcRef<Variable>>())
        .def_property("variable", &MathStructure::variable,
                      &MathStructure::setVariable);
  }

  void repr(std ::string &output) const {
    output += "MathStructure.Variable(variable=";
    output +=
        py::cast(this->variable()).attr("__repr__")().cast<std::string_view>();
    output += ")";
  }
};

class MathStructureFunctionProxy final : public MathStructure {
public:
  MathStructureFunctionProxy(QalcRef<MathFunction> function) : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_FUNCTION);
    setFunction(function.forget());
  }

  MathStructureFunctionProxy(QalcRef<MathFunction> &&function, py::args args)
      : MathStructureFunctionProxy(function) {
    for (auto arg : args) {
      auto *marg = arg.cast<MathStructure *>();
      marg->ref();
      addChild_nocopy(marg);
    }
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureFunctionProxy, Base> &c) {
    c.def(py::init<QalcRef<MathFunction>, py::args>(), py::arg("function"),
          py::pos_only{})
        .def_property_readonly("function",
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

class MathStructureUnitProxy final : public MathStructure {
public:
  MathStructureUnitProxy(Unit *unit) {
    PROXY_INIT;
    setType(STRUCT_UNIT);
    setUnit(unit);
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureUnitProxy, Base> &c) {
    c.def(py::init<Unit *>(), py::arg("unit"))
        .def_property_readonly("unit", [](MathStructureUnitProxy const &self) {
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

class MathStructurePowerProxy final : public MathStructure {
public:
  MathStructurePowerProxy(MathStructure *base, MathStructure *exponent)
      : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_POWER);
    PROXY_APPEND_CHILD_OPT(base, MathStructureRef::construct(0));
    PROXY_APPEND_CHILD_OPT(exponent, MathStructureRef::construct(0));
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructurePowerProxy, Base> &c) {
    c.def(py::init<MathStructure *, MathStructure *>(),
          py::arg("base") = static_cast<MathStructure *>(nullptr),
          py::arg("exponent") = static_cast<MathStructure *>(nullptr))
        PROXY_CHILD_ACCESSOR("base", 0) PROXY_CHILD_ACCESSOR("exponent", 1);
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

class MathStructureVectorProxy : public MathStructureSequence {
public:
  MathStructureVectorProxy() : MathStructureSequence() {
    PROXY_INIT;
    setType(STRUCT_VECTOR);
  }
  MathStructureVectorProxy(py::list items) : MathStructureVectorProxy() {
    for (auto item : items)
      _math_structure_append_child(*this, item.cast<MathStructureRef>());
  }

  using Base = MathStructureSequence;

  static void init(qalc_class_<MathStructureVectorProxy, Base> &c) {
    c.def(py::init<>()).def(py::init<py::list>());
    py::implicitly_convertible<py::list, MathStructureVectorProxy>();
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

class MathStructureUndefinedProxy : public MathStructure {
public:
  MathStructureUndefinedProxy() : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_UNDEFINED);
  }

  using Base = MathStructure;

  static void init(qalc_class_<MathStructureUndefinedProxy, Base> &c) {
    c.def(py::init<>());
  }

  void repr(std::string &output) const {
    output += "MathStructure.Undefined()";
  }
};

STUB_PROXY(Division);
