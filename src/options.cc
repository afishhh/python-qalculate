#include "options.hh"

std::optional<MathStructureRef> PEvaluationOptions::get_isolate_var() {
  if (isolate_var)
    return MathStructureRef(const_cast<MathStructure *>(isolate_var));
  else
    return std::nullopt;
}
void PEvaluationOptions::set_isolate_var(
    std::optional<MathStructureRef> value) {
  if (isolate_var)
    const_cast<MathStructure *>(isolate_var)->unref();

  if (value) {
    (*value)->ref();
    isolate_var = value->get();
  } else
    isolate_var = nullptr;
}
