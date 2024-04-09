#pragma once

#include <libqalculate/MathStructure.h>
#include <pybind11/pybind11.h>

template <typename T, class = void> struct QalcStructureInfo {};

template <typename T>
struct QalcStructureInfo<
    T, std::enable_if_t<std::is_base_of_v<MathStructure, T>>> {
  constexpr static bool init_starts_at_refcount_1 = true;
};

template <typename T>
struct QalcStructureInfo<
    T, std::enable_if_t<std::is_base_of_v<ExpressionItem, T>>> {
  constexpr static bool init_starts_at_refcount_1 = false;
};

template <typename T> class QalcRef {
  T *_ptr;

  QalcRef(T *structure, std::nullptr_t) : _ptr(structure) {}

  // for debugging
  inline void _ref_notify(int new_refs) {
    if (_ptr) {
      // std::cerr << "QalcPtr<" << typeid(T).name() << "> " << (void *)_ptr
      //           << "'s refs: " << new_refs;
      // std::cerr << '\n';
      (void)new_refs;
    }
  }

public:
  QalcRef() : _ptr(nullptr) {}
  QalcRef(std::nullptr_t) : _ptr(nullptr) {}
  explicit QalcRef(T *structure) : _ptr(structure) {
    structure->ref();
    _ref_notify(_ptr->refcount());
  }

  template <typename... Args> static QalcRef construct(Args &&...args) {
    if constexpr (QalcStructureInfo<T>::init_starts_at_refcount_1)
      return adopt(new T(std::forward<Args>(args)...));
    else
      return QalcRef(new T(std::forward<Args>(args)...));
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

  T *forget() {
    T *old = _ptr;
    _ptr = nullptr;
    return old;
  }

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
