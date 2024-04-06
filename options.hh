#pragma once

#include <libqalculate/includes.h>
#include <libqalculate/qalculate.h>
#include <optional>

class PEvaluationOptions final : public EvaluationOptions {
public:
  ~PEvaluationOptions() { delete isolate_var; }
  PEvaluationOptions() : EvaluationOptions() {}
  PEvaluationOptions(EvaluationOptions const &options)
      : EvaluationOptions(options) {}
  PEvaluationOptions(PEvaluationOptions &&other)
      : EvaluationOptions(std::move(other)) {
    other.isolate_var = nullptr;
  };
  PEvaluationOptions &operator=(PEvaluationOptions &&other) {
    *(EvaluationOptions *)(this) = std::move(other);
    other.isolate_var = nullptr;
    return *this;
  };
  PEvaluationOptions(PEvaluationOptions const &) = delete;
  PEvaluationOptions &&operator=(PEvaluationOptions const &) = delete;

  MathStructure *get_isolate_var();
  void set_isolate_var(MathStructure const *value);
};
