#pragma once

#include <libqalculate/includes.h>
#include <libqalculate/qalculate.h>
#include <optional>

#include "ref.hh"

class PEvaluationOptions final : public EvaluationOptions {
public:
  ~PEvaluationOptions() {
    if (isolate_var)
      const_cast<MathStructure *>(isolate_var)->unref();
  }
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

  PEvaluationOptions(PEvaluationOptions const &other)
      : EvaluationOptions(other) {
    if (this->isolate_var)
      const_cast<MathStructure *>(this->isolate_var)->ref();
  }
  PEvaluationOptions &operator=(PEvaluationOptions const &other) {
    *(EvaluationOptions *)(this) = other;
    if (this->isolate_var)
      const_cast<MathStructure *>(this->isolate_var)->ref();
    return *this;
  }

  std::optional<MathStructureRef> get_isolate_var();
  void set_isolate_var(std::optional<MathStructureRef>);
};

class PAssumptions final : public Assumptions {
public:
  ~PAssumptions() {
    delete fmin;
    delete fmax;
  }
};
