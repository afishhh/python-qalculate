#include "options.hh"

MathStructure *PEvaluationOptions::get_isolate_var() {
  std::cerr << ">" << isolate_var << '\n';
  // Why is this even const?
  return const_cast<MathStructure *>(isolate_var);
}
void PEvaluationOptions::set_isolate_var(MathStructure const *value) {
  delete isolate_var;
  if (value)
    isolate_var = new MathStructure(value);
  else
    isolate_var = nullptr;
  std::cerr << "=" << isolate_var << '\n';
}
