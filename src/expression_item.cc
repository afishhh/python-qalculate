#include "expression_items.hh"
#include "wrappers.hh"

#include <libqalculate/ExpressionItem.h>
#include <limits>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

py::class_<ExpressionName> add_expression_name(py::module_ &m) {
  return add_expression_name_auto(m)
      .def(py::init())
      .def(py::init<std::string>(), py::arg("name"), py::pos_only{})
      .def(py::self == py::self)
      .def_property_readonly("underscore_removal_allowed",
                             &ExpressionName::underscoreRemovalAllowed)
      // TODO: generate formatted name (abstract away some parsing)
      ;
}

class ExpressionNamesProxy {
  QalcRef<ExpressionItem> _parent;

public:
  ExpressionNamesProxy(QalcRef<ExpressionItem> &&parent)
      : _parent(std::move(parent)) {}

  ExpressionName const &get(size_t idx) const {
    auto &result = _parent->getName(idx + 1);
    if (&result == &empty_expression_name)
      throw py::index_error();

    return result;
  }

  size_t size() const { return _parent->countNames(); }
};

template <typename Ret, typename... Args>
std::pair<Ret (*)(Args..., void *), void *>
make_function_pointer_pair(std::function<Ret(Args...)> const &function) {
  if (!function)
    return {nullptr, nullptr};

  return {[](Args... args, void *function) {
            return (*(std::function<Ret(Args...)> *)function)(args...);
          },
          (void *)&function};
}

#define DEF_PREFERRED_NAME(py_name, cpp_name)                                  \
  def(                                                                         \
      py_name,                                                                 \
      [](ExpressionItem const &self, bool abbreviation, bool use_unicode,      \
         bool plural, bool reference,                                          \
         std::function<bool(char const *)> can_display_unicode_string)         \
          -> std::optional<std::reference_wrapper<ExpressionName const>> {     \
        auto [fun, data] =                                                     \
            make_function_pointer_pair(can_display_unicode_string);            \
        auto &result = self.cpp_name(abbreviation, use_unicode, plural,        \
                                     reference, fun, data);                    \
        if (&result == &empty_expression_name)                                 \
          return std::nullopt;                                                 \
        return std::ref(result);                                               \
      },                                                                       \
      py::return_value_policy::reference_internal,                             \
      py::arg("abbreviation") = false, py::arg("use_unicode") = false,         \
      py::arg("plural") = false, py::arg("reference") = false,                 \
      py::arg("can_display_unicode_string") =                                  \
          static_cast<std::function<bool(char const *)>>(nullptr))

#define DEF_EXPRESSION_ITEM_GETTER(fun, type)                                  \
  def_static(                                                                  \
      "get",                                                                   \
      [](std::string_view name) -> QalcRef<type> {                             \
        /* TODO: How useful is the second argument? */                         \
        auto ptr = (fun)(std::string(name));                                   \
        if (!ptr)                                                              \
          throw py::key_error(#type " with name " + std::string(name) +        \
                              " does not exist");                              \
        return QalcRef(ptr);                                                   \
      },                                                                       \
      py::arg("name"), py::pos_only{})

qalc_class_<ExpressionItem> add_expression_item(py::module_ &m) {
  py::class_<ExpressionNamesProxy>(m, "_ExpressionNames")
      .def("__getitem__", &ExpressionNamesProxy::get, py::is_operator{})
      .def("__len__", &ExpressionNamesProxy::size, py::is_operator{});

  return add_expression_item_properties(
             qalc_class_<ExpressionItem>(m, "ExpressionItem")
                 .def_property_readonly("names",
                                        [](QalcRef<ExpressionItem> item) {
                                          return ExpressionNamesProxy(
                                              std::move(item));
                                        }))

      .DEF_EXPRESSION_ITEM_GETTER(CALCULATOR->getExpressionItem, ExpressionItem)

      // NOTE: While this function does accept extra arguments in libqalculate
      //       I think it can be replaced by the "findName" function instead.
      //       Therefore this can just be a property while findName can be used
      //       for more complex searches.
      .def_property_readonly(
          "name", [](ExpressionItem const &self) { return self.name(); })
      .DEF_PREFERRED_NAME("preferred_name", preferredName)
      .DEF_PREFERRED_NAME("preferred_input_name", preferredInputName)
      .DEF_PREFERRED_NAME("preferred_display_name", preferredDisplayName)
      .def_property(
          "title",
          [](ExpressionItem const &self) -> std::string {
            return self.title(false);
          },
          [](ExpressionItem &self, std::string_view title) {
            self.setTitle(std::string(title));
          })
      .def(
          "find_name",
          [](ExpressionItem const &item, std::optional<bool> abbreviation,
             std::optional<bool> use_unicode, std::optional<bool> plural,
             std::function<bool(char const *)> can_display_unicode_string)
              -> ExpressionName const & {
            int i_abbreviation =
                abbreviation.has_value() ? abbreviation.value() : -1;
            int i_use_unicode =
                use_unicode.has_value() ? use_unicode.value() : -1;
            int i_plural = plural.has_value() ? plural.value() : -1;

            auto [fun, data] =
                make_function_pointer_pair(can_display_unicode_string);
            auto &result = item.findName(i_abbreviation, i_use_unicode,
                                         i_plural, fun, data);

            if (&result == &empty_expression_name)
              throw py::key_error("Name not found");
            return result;
          },
          py::return_value_policy::reference_internal, py::kw_only{},
          py::arg("abbreviation") =
              static_cast<std::optional<bool>>(std::nullopt),
          py::arg("use_unicode") =
              static_cast<std::optional<bool>>(std::nullopt),
          py::arg("plural") = static_cast<std::optional<bool>>(std::nullopt),
          py::arg("can_display_unicode_string") =
              static_cast<std::function<bool(char const *)>>(nullptr));
}

qalc_class_<MathFunction> add_math_function(py::module_ &m) {
  return qalc_class_<MathFunction, ExpressionItem>(m, "MathFunction")
      .def(py::init([](MathStructureFunctionProxy mstruct) {
             return QalcRef<MathFunction>(mstruct.function());
           }),
           py::arg("math_structure"), py::pos_only{})
      .DEF_EXPRESSION_ITEM_GETTER(CALCULATOR->getFunction, MathFunction)
      .def(
          "calculate",
          [](MathFunction &self, py::args args,
             PEvaluationOptions const &options) {
            MathStructure vargs;
            vargs.setType(STRUCT_VECTOR);
            for (auto arg : args) {
              auto *marg = arg.cast<MathStructure *>();
              marg->ref();
              vargs.addChild_nocopy(marg);
            }

            return MathStructureRef::construct(
                self.calculate(vargs, (EvaluationOptions const &)options));
          },
          py::arg("options") = PEvaluationOptions())
      .def("calculate", [](MathFunction &self, MathStructureVectorProxy &vargs,
                           PEvaluationOptions const &options) {
        return MathStructureRef::construct(self.calculate(
            (MathStructure &)vargs, (EvaluationOptions const &)options));
      });
}

py::class_<PAssumptions> &add_assumptions(py::module_ &m) {
  return add_assumptions_properties(
      py::class_<PAssumptions>(m, "Assumptions")
          .def(py::init([](AssumptionType type, AssumptionSign sign) {
                 PAssumptions assumptions;
                 assumptions.setType(type);
                 assumptions.setSign(sign);
                 return assumptions;
               }),
               py::arg("type") = ASSUMPTION_TYPE_NUMBER,
               py::arg("sign") = ASSUMPTION_SIGN_UNKNOWN));
}

qalc_class_<Variable> add_variable(py::module_ &m) {
  return qalc_class_<Variable, ExpressionItem>(m, "Variable")
      .DEF_EXPRESSION_ITEM_GETTER(CALCULATOR->getVariable, Variable)
      .def_property_readonly("is_known", &Variable::isKnown);
}

qalc_class_<UnknownVariable> add_unknown_variable(py::module_ &m) {
  return qalc_class_<UnknownVariable, Variable>(m, "UnknownVariable")
      .def_property(
          "assumptions", &UnknownVariable::assumptions,
          [](UnknownVariable &self, Assumptions const &assumptions) {
            self.setAssumptions(new Assumptions(assumptions));
          },
          py::return_value_policy::copy)
      .def_property("interval", &UnknownVariable::interval,
                    &UnknownVariable::setInterval);
}

qalc_class_<Unit> add_unit(py::module_ &m) {
  return add_unit_properties(
      qalc_class_<Unit, ExpressionItem>(m, "Unit")
          .DEF_EXPRESSION_ITEM_GETTER(CALCULATOR->getUnit, Unit)

          .def_property_readonly_static(
              "DEGREE",
              [](py::handle) { return QalcRef(CALCULATOR->getDegUnit()); })

          .def_property_readonly_static(
              "GRADIAN", [](py::handle) { return QalcRef(CALCULATOR->getGraUnit()); })

          .def_property_readonly_static(
              "RADIAN", [](py::handle) { return QalcRef(CALCULATOR->getRadUnit()); })

          .def_property_readonly(
              "is_si", [](Unit const &self) { return self.isSIUnit(); })
          .def_property(
              "system", [](Unit const &self) { return self.system(); },
              [](Unit &self, std::string_view system) {
                // The docsting for setSystem says that setting to "SI"
                // case-insensitively is equivalent to setAsSIUnit().
                // But the implementation is missing a check for this single
                // case...
                if (system == "sI")
                  self.setAsSIUnit();
                else
                  self.setSystem(std::string(system));
              }));
}
