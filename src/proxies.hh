#pragma once

#include <cassert>
#include <concepts>
#include <libqalculate/MathStructure.h>
#include <libqalculate/qalculate.h>
#include <pybind11/cast.h>
#include <pybind11/pybind11.h>
#include <pybind11/typing.h>
#include <string_view>

namespace py = pybind11;

#include "ref.hh"

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
            py::is_operator{})
        .def("__repr__", [](MathStructure const &self) {
          return std::string("MathStructure.Number(") + self.number().print() +
                 std::string(")");
        });
  }
};

template <size_t MIN_ITEMS>
class MathStructureGenericOperationProxy : public MathStructure {
protected:
  template <typename T>
  static void init(qalc_class_<T> &c) {
    c.def(py::init<py::typing::List<MathStructure>>(), py::arg("children") = py::list());
  }

public:
  MathStructureGenericOperationProxy(py::typing::List<MathStructure> list) {
    PROXY_INIT;

    if (list.size() < MIN_ITEMS)
      throw py::value_error("At least " + std::to_string(MIN_ITEMS) +
                            " are requried for this node");

    for (auto value : list) {
      auto structure = value.cast<MathStructureRef>();
      PROXY_APPEND_CHILD(structure);
    }
  }
};

#define GENERIC_OPERATION_PROXY(proxy, nitems)                                 \
  class proxy final : public MathStructureGenericOperationProxy<nitems> {      \
  public:                                                                      \
    static void init(qalc_class_<proxy> &c) {                                  \
      MathStructureGenericOperationProxy::init(c);                             \
    }                                                                          \
  }

#define STUB_PROXY(proxy)                                                      \
  class proxy final : public MathStructure {                                   \
  public:                                                                      \
    static void init(qalc_class_<proxy> &) {}                                  \
  }

GENERIC_OPERATION_PROXY(MathStructureMultiplicationProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureAdditionProxy, 0);

GENERIC_OPERATION_PROXY(MathStructureBitwiseAndProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureBitwiseOrProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureBitwiseXorProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureBitwiseNotProxy, 0);

GENERIC_OPERATION_PROXY(MathStructureLogicalAndProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureLogicalOrProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureLogicalXorProxy, 0);
GENERIC_OPERATION_PROXY(MathStructureLogicalNotProxy, 0);

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
          py::arg("left") = static_cast<MathStructure*>(nullptr),
          py::arg("type") = ComparisonType::COMPARISON_EQUALS,
          py::arg("right") = static_cast<MathStructure*>(nullptr)) PROXY_CHILD_ACCESSOR("left", 0)
        PROXY_CHILD_ACCESSOR("right", 1)
            .def_property("comparisonType", &MathStructure::comparisonType,
                          &MathStructure::setComparisonType);
  }
};

STUB_PROXY(MathStructureDatetimeProxy);
STUB_PROXY(MathStructureVariableProxy);
STUB_PROXY(MathStructureFunctionProxy);
STUB_PROXY(MathStructureSymbolicProxy);
STUB_PROXY(MathStructureUnitProxy);

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
          py::arg("base") = static_cast<MathStructure*>(nullptr), py::arg("exponent") = static_cast<MathStructure*>(nullptr))
        PROXY_CHILD_ACCESSOR("base", 0) PROXY_CHILD_ACCESSOR("exponent", 1);
  }
};

STUB_PROXY(MathStructureNegateProxy);
STUB_PROXY(MathStructureInverseProxy);
STUB_PROXY(MathStructureVectorProxy);

class MathStructureUndefinedProxy : public MathStructure {
public:
  MathStructureUndefinedProxy() : MathStructure() {
    PROXY_INIT;
    setType(STRUCT_UNDEFINED);
  }

  static void init(qalc_class_<MathStructureUndefinedProxy> &c) {
    c.def(py::init<>());
  }
};

STUB_PROXY(MathStructureDivisionProxy);
