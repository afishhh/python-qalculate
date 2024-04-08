#pragma once

#include <cassert>
#include <concepts>
#include <libqalculate/MathStructure.h>
#include <libqalculate/qalculate.h>
#include <pybind11/cast.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <pybind11/typing.h>
#include <string_view>

namespace py = pybind11;

#include "ref.hh"

// FIXME: split up generated.hh into separate files
void MathStructure_repr(MathStructure const *mstruct, std::string &output);

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

class MathStructureNumberProxy final : public MathStructure {
public:
  MathStructureNumberProxy() : MathStructure(0) { PROXY_INIT; }
  MathStructureNumberProxy(Number const &number) : MathStructure(number) {
    PROXY_INIT;
  }

  static void init(qalc_class_<MathStructureNumberProxy> &c) {
    c.def(py::init<>())
        .def(py::init<Number>())
        .def_property("value",
                      (Number & (MathStructure ::*)()) & MathStructure::number,
                      [](MathStructureNumberProxy &self, Number const &value) {
                        self.number().set(value);
                      })
        .def(
            "__str__",
            [](MathStructure const &self) { return self.number().print(); },
            py::is_operator{});
  }

  void repr(std::string &output) const {
    output += "MathStructure.Number(";
    output += this->number().print();
    output += ")";
  }
};

template <size_t MIN_ITEMS, typename Self>
class MathStructureGenericOperationProxy : public MathStructure {
protected:
  template <typename T> static void init(qalc_class_<T> &c) {
    c.def(py::init<py::typing::List<MathStructure>>(),
          py::arg("children") = py::list());
  }

public:
  MathStructureGenericOperationProxy(py::typing::List<MathStructure> list) {
    PROXY_INIT;

    if (list.size() < MIN_ITEMS)
      throw py::value_error("At least " + std::to_string(MIN_ITEMS) +
                            " are requried for this node");

    m_type = Self::TYPE;
    for (auto value : list) {
      auto structure = value.cast<MathStructureRef>();
      PROXY_APPEND_CHILD(structure);
    }
  }

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
    static void init(qalc_class_<proxy> &c) {                                  \
      MathStructureGenericOperationProxy::init(c);                             \
    }                                                                          \
  }

#define GENERIC_OPERATION_PROXY(name, type, nitems)                            \
  GENERIC_OPERATION_PROXY1(MathStructure##name##Proxy, type,                   \
                           "MathStructure." #name, nitems)

#define STUB_PROXY(name)                                                       \
  class MathStructure##name##Proxy final : public MathStructure {              \
  public:                                                                      \
    static void init(qalc_class_<MathStructure##name##Proxy> &) {}             \
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

class MathStructureComparisonProxy : public MathStructure {
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

  static void init(qalc_class_<MathStructureComparisonProxy> &c) {
    c.def(py::init<MathStructure *, ComparisonType, MathStructure *>(),
          py::arg("left") = static_cast<MathStructure *>(nullptr),
          py::arg("type") = ComparisonType::COMPARISON_EQUALS,
          py::arg("right") = static_cast<MathStructure *>(nullptr))
        PROXY_CHILD_ACCESSOR("left", 0) PROXY_CHILD_ACCESSOR("right", 1)
            .def_property("comparisonType", &MathStructure::comparisonType,
                          &MathStructure::setComparisonType);
  }

  void repr(std::string &output) const {
    output += "MathStructure.Comparison(left=";
    MathStructure_repr(&(*this)[0], output);
    output += ", type=";
    output +=
        ((py::object)py::cast(this->comparisonType())).attr("__repr__")().cast<std::string>();
    output += ", right=";
    MathStructure_repr(&(*this)[1], output);
    output += ")";
  }
};

STUB_PROXY(Datetime);
STUB_PROXY(Variable);
STUB_PROXY(Function);
STUB_PROXY(Symbolic);
STUB_PROXY(Unit);

class MathStructurePowerProxy : public MathStructure {
public:
  MathStructurePowerProxy(MathStructure *base, MathStructure *exponent)
      : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_POWER);
    PROXY_APPEND_CHILD_OPT(base, MathStructureRef::construct(0));
    PROXY_APPEND_CHILD_OPT(exponent, MathStructureRef::construct(0));
  }

  static void init(qalc_class_<MathStructurePowerProxy> &c) {
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
STUB_PROXY(Vector);

class MathStructureUndefinedProxy : public MathStructure {
public:
  MathStructureUndefinedProxy() : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_UNDEFINED);
  }

  static void init(qalc_class_<MathStructureUndefinedProxy> &c) {
    c.def(py::init<>());
  }

  void repr(std::string &output) const {
    output += "MathStructure.Undefined()";
  }
};

STUB_PROXY(Division);
