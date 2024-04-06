#include <cassert>
#include <libqalculate/qalculate.h>
#include <pybind11/attr.h>
#include <pybind11/cast.h>
#include <pybind11/gil.h>
#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <pybind11/stl.h>
#include <string_view>

namespace py = pybind11;

#include "generated.hh"
#include "options.hh"
#include "proxies.hh"
#include "ref.hh"

Number number_from_python_int(py::int_ value) {
  int overflow;
  long long long_value = PyLong_AsLongLongAndOverflow(value.ptr(), &overflow);
  if (overflow != 0) {
    py::object positive;
    if (overflow < 0) {
      PyObject *result = PyNumber_Absolute(value.ptr());
      if (result == nullptr)
        throw py::error_already_set();
      positive = py::cast<py::object>(result);
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

class ChildrenList {
  MathStructureRef _parent;

public:
  ChildrenList(MathStructureRef &&parent) : _parent(std::move(parent)) {}

  void append(MathStructure *other) {
    other->ref();
    _parent->addChild_nocopy(other);
  }

  MathStructure *get_item(size_t idx) {
    if (idx >= _parent->size())
      throw py::index_error();
    return &(*_parent)[idx];
  }

  size_t size() { return _parent->size(); }
};

MathStructureRef calculate(MathStructure const &mstruct,
                           PEvaluationOptions const &options,
                           std::string to_str) {
  MathStructure result;
  {
    py::gil_scoped_release _gil;
    result = CALCULATOR->calculate(mstruct, options, to_str);
  }
  return MathStructureRef::adopt(result);
}

PYBIND11_MODULE(qalculate, m) {
  m.doc() = "Python bindings for libqalculate";

  new Calculator();

  // TODO: Properties somewhere?
  m.def("get_precision", []() { return CALCULATOR->getPrecision(); });
  m.def("set_precision",
        [](int precision) { CALCULATOR->setPrecision(precision); });

  add_all_enums(m);

#define DEF_COMPARISON_HELPER(name, macro)                                     \
  .def_property_readonly(name,                                                 \
                         [](ComparisonResult self) { return macro(self); })

  // clang-format off
  // Values are defined in add_all_enums
  add_comparison_result_enum(m)
    DEF_COMPARISON_HELPER("might_be_less_or_greater", COMPARISON_MIGHT_BE_LESS_OR_GREATER)
    DEF_COMPARISON_HELPER("not_fully_known", COMPARISON_NOT_FULLY_KNOWN)
    DEF_COMPARISON_HELPER("is_equal_or_greater", COMPARISON_IS_EQUAL_OR_GREATER)
    DEF_COMPARISON_HELPER("is_equal_or_less", COMPARISON_IS_EQUAL_OR_LESS)
    DEF_COMPARISON_HELPER("is_not_equal", COMPARISON_IS_NOT_EQUAL)
    DEF_COMPARISON_HELPER("might_be_equal", COMPARISON_MIGHT_BE_EQUAL)
    DEF_COMPARISON_HELPER("might_be_not_equal", COMPARISON_MIGHT_BE_NOT_EQUAL);
  // clang-format on

  add_sort_options(m);
  add_print_options(m);
  add_parse_options(m);
  add_evaluation_options(m);

#define COMMON_ARITHMETIC_OPERATORS(other)                                     \
  .def(py::self *other)                                                        \
      .def(py::self *= other)                                                  \
      .def(py::self / other)                                                   \
      .def(decltype(py::self)() /= other)                                      \
      .def(py::self + other)                                                   \
      .def(py::self += other)                                                  \
      .def(py::self - other)                                                   \
      .def(decltype(py::self)() -= other)                                      \
      .def(py::self ^ other)                                                   \
      .def(decltype(py::self)() ^= other)                                      \
                                                                               \
      .def(py::self == other)                                                  \
      .def(py::self != other)

  auto number = add_number_properties(
      py::class_<Number>(m, "Number")
          .def(py::init<>())
          .def(py::init(&number_from_python_int))
          .def(py::init([](long double value) {
            Number number;
            number.setFloat(value);
            return number;
          }))

          .def(
              "__str__", [](Number const &self) { return self.print(); },
              py::is_operator())

              COMMON_ARITHMETIC_OPERATORS(py::self)

          .def(-py::self)
          .def(!py::self)
          .def(py::self < py::self)
          .def(py::self <= py::self)
          .def(py::self > py::self)
          .def(py::self >= py::self));

  py::implicitly_convertible<py::int_, Number>();

  py::class_<ChildrenList>(m, "_MathStructureChildren")
      // FIXME: how to expose this safely?
      .def("append", &ChildrenList::append)
      .def("__getitem__", &ChildrenList::get_item, py::is_operator{})
      .def("__len__", &ChildrenList::size, py::is_operator{});

  add_math_structure_proxies(add_math_structure_properties(
      qalc_class_<MathStructure>(m, "MathStructure")
          .def(py::init([]() {
            throw std::runtime_error(
                "MathStructure is an abstract type, construct specific "
                "subclasses directly instead.");
            return MathStructureRef::construct();
          }))

          .def_property_readonly("children",
                                 [](MathStructure *self) {
                                   return ChildrenList(MathStructureRef(self));
                                 })

          .def(-py::self)
          .def(!py::self)

              COMMON_ARITHMETIC_OPERATORS(py::self)
                  COMMON_ARITHMETIC_OPERATORS(Number())

          // .def(
          //     "__repr__",
          //     [](MathStructure const &self) {
          //       std::string result = "MathStructure(\"";
          //       for (auto x : self.print(PrintOptions())) {
          //         if (x == '\"')
          //           result += "\\\"";
          //         else if (x == '\\')
          //           result += "\\\\";
          //         else
          //           result += x;
          //       }
          //       result += "\")";
          //       return result;
          //     },
          //     py::is_operator{})

          .def("compare", &MathStructure::compare)
          .def("compare_approximately", &MathStructure::compareApproximately)

          .def_static(
              "parse",
              [](std::string_view s) {
                return MathStructureRef::adopt(
                    CALCULATOR->parse(std::string(s)));
              },
              py::arg("value"), py::pos_only{})

          .def("calculate", &calculate,
               py::arg("options") =
                   PEvaluationOptions(default_evaluation_options),
               py::arg("to_str") = "")

          .def(
              "print",
              [](MathStructure &s, PrintOptions const &options) {
                return s.print(options);
              },
              py::arg("options") = default_print_options)));

  number.def(py::init([](MathStructureNumberProxy const &structure) {
    return structure.number();
  }));

  m.def("get_message_print_options",
        []() { return CALCULATOR->messagePrintOptions(); });

  m.def("set_message_print_options",
        [](PrintOptions &opts) { CALCULATOR->setMessagePrintOptions(opts); });

  m.def("calculate", &calculate, py::arg("mstruct"), py::pos_only{},
        py::arg("options") = PEvaluationOptions(default_evaluation_options),
        py::arg("to_str") = "");

  m.def(
      "calculate",
      [](std::string expression, PEvaluationOptions const &options,
         std::string to) {
        return calculate(CALCULATOR->parse(expression, options.parse_options),
                         options, to);
      },
      py::arg("mstruct"),
      py::arg("options") = PEvaluationOptions(default_evaluation_options),
      py::arg("to") = "");

  m.def(
      "calculate_and_print",
      [](std::string expression, PEvaluationOptions const &eval_options,
         PrintOptions const &print_options) {
        py::gil_scoped_release _gil;
        std::string result = CALCULATOR->calculateAndPrint(
            expression, -1, eval_options, print_options);
        assert(!CALCULATOR->aborted());
        return result;
      },
      py::arg("expression"),
      py::arg("eval_options") =
          PEvaluationOptions(default_user_evaluation_options),
      py::arg("print_options") = default_print_options);

  py::class_<CalculatorMessage>(m, "Message")
      .def_property_readonly("text", &CalculatorMessage::c_message)
      .def_property_readonly("type", &CalculatorMessage::type);

  m.def("take_messages", []() {
    std::vector<CalculatorMessage> messages;
    while (true) {
      CalculatorMessage *msg = CALCULATOR->message();
      if (!msg)
        return messages;
      messages.emplace_back(std::move(*msg));
      CALCULATOR->nextMessage();
    }
  });

  auto loaders =
      std::initializer_list<std::pair<char const *, bool (Calculator::*)()>>{
          {"load_global_prefixes", &Calculator::loadGlobalPrefixes},
          {"load_global_currencies", &Calculator::loadGlobalCurrencies},
          {"load_global_units", &Calculator::loadGlobalUnits},
          {"load_global_variables", &Calculator::loadGlobalVariables},
          {"load_global_functions", &Calculator::loadGlobalFunctions},
          {"load_global_dataSets", &Calculator::loadGlobalDataSets},
      };
  for (auto [name, fun] : loaders)
    m.def(name, [fun] {
      if (!(*CALCULATOR.*fun)())
        throw std::runtime_error("qalculate failed to load something");
    });
}
