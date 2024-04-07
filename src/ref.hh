#pragma once

#include <libqalculate/MathStructure.h>
#include <pybind11/pybind11.h>

template <typename T> class QalcRef {
  T *_ptr;

  QalcRef(T *structure, std::nullptr_t) : _ptr(structure) {}

  // for debugging
  inline void _ref_notify(int new_refs) {
    // if (_ptr)
    //   std::cerr << (void *)_ptr << "'s refs: " << new_refs << '\n';
    (void)new_refs;
  }

public:
  QalcRef() : _ptr(nullptr) {}
  QalcRef(std::nullptr_t) : _ptr(nullptr) {}
  QalcRef(T *structure) : _ptr(structure) {
    structure->ref();
    _ref_notify(_ptr->refcount());
  }

  template <typename... Args> static QalcRef construct(Args &&...args) {
    return adopt(new T(std::forward<Args>(args)...));
  }

  static QalcRef adopt(T *structure) { return QalcRef(structure, nullptr); }

  // FIXME: Is this something we want to do?
  static QalcRef adopt(T structure) {
    return QalcRef(new T(structure), nullptr);
  }

  QalcRef(QalcRef &&other) : _ptr(other._ptr) { other._ptr = nullptr; }

  QalcRef &operator=(QalcRef &&other) {
    ~QalcRef();
    _ptr = other._ptr;
    other.ptr = nullptr;
    return *this;
  }

  QalcRef(QalcRef const &other) : _ptr(other._ptr) {
    _ptr->ref();
    _ref_notify(_ptr->refcount());
  }

  QalcRef &operator=(QalcRef const &other) {
    this->~QalcRef();
    _ptr = other._ptr;
    _ptr->ref();
    _ref_notify(_ptr->refcount());
    return *this;
  }

  void forget() { _ptr = nullptr; }

  ~QalcRef() {
    if (_ptr) {
      _ref_notify(_ptr->refcount() - 1);
      _ptr->unref();
    }
  }

  T *get() const { return _ptr; }
  T &operator*() const { return *_ptr; }
  T *operator->() const { return _ptr; }
  operator T *() const { return _ptr; }
  operator bool() const { return _ptr; }
};

using MathStructureRef = QalcRef<MathStructure>;

PYBIND11_DECLARE_HOLDER_TYPE(T, QalcRef<T>, true)

template <typename T, typename... Args>
using qalc_class_ = pybind11::class_<T, QalcRef<T>, Args...>;
