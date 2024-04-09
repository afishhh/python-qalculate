#include "expression_item.hh"

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
      .def_static(
          "get",
          [](std::string_view name) -> std::optional<ExpressionItem *> {
            // TODO: How useful is the second argument?
            auto ptr = CALCULATOR->getExpressionItem(std::string(name));
            if (!ptr)
              return std::nullopt;
            return ptr;
          },
          py::arg("name"))
      // NOTE: While this function does accept extra arguments in libqalculate
      //       I think it can be replaced by the "findName" function instead.
      //       Therefore this can just be a property while findName can be used
      //       for more complex searches.
      .def_property_readonly(
          "name", [](ExpressionItem const &item) { return item.name(); })
      // TODO: can_display_unicode_string_function
      .def(
          "findName",
          [](ExpressionItem const &item, std::optional<bool> abbreviation,
             std::optional<bool> use_unicode, std::optional<bool> plural,
             std::function<bool(char const *)> can_display_unicode_string)
              -> std::optional<std::reference_wrapper<ExpressionName const>> {
            int i_abbreviation =
                abbreviation.has_value() ? abbreviation.value() : -1;
            int i_use_unicode =
                use_unicode.has_value() ? use_unicode.value() : -1;
            int i_plural = plural.has_value() ? plural.value() : -1;

            ExpressionName const *result;
            if (!can_display_unicode_string)
              result = &item.findName(i_abbreviation, i_use_unicode, i_plural);
            result = &item.findName(
                i_abbreviation, i_use_unicode, i_plural,
                [](char const *str, void *fun) {
                  return (*(std::function<bool(char const *)> *)fun)(str);
                },
                &can_display_unicode_string);

            if (result == &empty_expression_name)
              return std::nullopt;
            return {std::ref(*result)};
          },
          py::return_value_policy::reference_internal, py::kw_only{},
          py::arg("abbreviation") =
              static_cast<std::optional<bool>>(std::nullopt),
          py::arg("use_unicode") =
              static_cast<std::optional<bool>>(std::nullopt),
          py::arg("plural") = static_cast<std::optional<bool>>(std::nullopt),
          py::arg("can_display_unicode_string") =
              std::function<bool(char const *)>(nullptr));
}
