from typing import ClassVar, overload

class Number:
    def __init__(self, value: _NumberConstructibleFrom) -> None: ...

    PLUS_INFINITY: ClassVar[Number]
    MINUS_INFINITY: ClassVar[Number]

    def print(self, options: PrintOptions = ...) -> str: ...
    def __int__(self) -> int: ...
    def __float__(self) -> float: ...
    def __complex__(self) -> complex: ...
    def __repr__(self) -> str: ...
    def __eq__(self, __value: object) -> bool: ...

class ExpressionItem:
    @staticmethod
    def get(name: str) -> ExpressionItem: ...

class MathFunction(ExpressionItem):
    @staticmethod
    def get(name: str) -> MathFunction: ...
    def calculate(self, *args: "MathStructure") -> MathStructure:
        pass

class Variable(ExpressionItem):
    @staticmethod
    def get(name: str) -> Variable: ...

class UnknownVariable(Variable):
    @property
    def assumptions(self) -> Assumptions: ...
    @assumptions.setter
    def assumptions(self, value: Assumptions) -> None: ...
    @property
    def interval(self) -> MathStructure: ...
    @interval.setter
    def interval(self, value: MathStructure) -> None: ...

class Unit(ExpressionItem):
    @staticmethod
    def get(name: str) -> Unit: ...

    DEGREE: ClassVar[Unit]
    RADIAN: ClassVar[Unit]
    GRADIAN: ClassVar[Unit]

class MathStructure:
    def __init__(self, value: _MathStructureConstructibleFrom): ...

    def compare(self, other: MathStructure) -> ComparisonResult: ...
    def compare_approximately(
        self, other: MathStructure, options: EvaluationOptions = ...
    ) -> ComparisonResult: ...
    def calculate(
        self, options: EvaluationOptions = ..., to: str = ""
    ) -> MathStructure: ...
    def print(self, options: PrintOptions = ...) -> str: ...
    def __eq__(self, __value: object) -> bool: ...

    class Number(MathStructure):
        def __init__(self, value: Number) -> None: ...
        def __int__(self) -> int: ...
        def __float__(self) -> float: ...
        def __complex__(self) -> complex: ...
        @property
        def value(self) -> Number: ...
        def __repr__(self) -> str: ...

    class Sequence(MathStructure):
        def __init__(self, children: Sequence[MathStructure]) -> None: ...

        def append(self, item: "MathStructure") -> None: ...
        def __delitem__(self, idx: int) -> None: ...

    def __len__(self) -> int: ...
    @overload
    def __getitem__(self, idx: int) -> "MathStructure": ...
    @overload
    def __getitem__(self, slice: slice) -> "MathStructure": ...
    def __repr__(self) -> str: ...

    class Multiplication(Sequence):
        pass

    class Addition(Sequence):
        pass

    class BitwiseAnd(Sequence):
        pass

    class BitwiseOr(Sequence):
        pass

    class BitwiseXor(Sequence):
        pass

    class BitwiseNot(Sequence):
        pass

    class LogicalAnd(Sequence):
        pass

    class LogicalOr(Sequence):
        pass

    class LogicalXor(Sequence):
        pass

    class LogicalNot(Sequence):
        pass

    class Comparison(MathStructure):
        def __init__(
            self,
            left: MathStructure = MathStructure.Number(0),
            type: ComparisonType = ComparisonType.EQUALS,
            right: MathStructure = MathStructure.Number(0),
        ) -> None: ...
        @property
        def left(self) -> MathStructure: ...
        @property
        def type(self) -> ComparisonType: ...
        @property
        def right(self) -> MathStructure: ...

    class Variable(MathStructure):
        def __init__(self, variable: Variable) -> None: ...
        @property
        def variable(self) -> Variable: ...

    class Function(MathStructure):
        def __init__(self, function: MathFunction, *args: MathStructure) -> None: ...
        @property
        def function(self) -> MathFunction: ...

    class Unit(MathStructure):
        def __init__(self, unit: Unit) -> None: ...
        @property
        def unit(self) -> Unit: ...

    class Power(MathStructure):
        def __init__(self, base: MathStructure, exponent: MathStructure) -> None: ...
        @property
        def base(self) -> MathStructure: ...
        @property
        def exponent(self) -> MathStructure: ...

    class Undefined(MathStructure):
        def __init__(self) -> None: ...

    # TODO: STUBS
    class DateTime(MathStructure):
        pass

    class Symbolic(MathStructure):
        pass

    class Negate(MathStructure):
        pass

    class Inverse(MathStructure):
        pass

    class Vector(MathStructure):
        @overload
        def __init__(self) -> None: ...
        @overload
        def __init__(self, values: Sequence[MathStructure]) -> None: ...

    class Division(MathStructure):
        pass

def calculate(
    expression: MathStructure | str, options: EvaluationOptions = ..., to: str = ""
) -> MathStructure: ...
def calculate_and_print(
    expression: str,
    eval_options: EvaluationOptions = ...,
    print_options: PrintOptions = ...,
) -> str: ...
def get_global_evaluation_options() -> EvaluationOptions: ...
def get_global_parse_options() -> ParseOptions: ...
def get_global_print_options() -> PrintOptions: ...
def get_global_sort_options() -> SortOptions: ...
def get_message_print_options() -> PrintOptions: ...
def get_precision() -> int: ...
def load_global_currencies() -> None: ...
def load_global_dataSets() -> None: ...
def load_global_functions() -> None: ...
def load_global_prefixes() -> None: ...
def load_global_units() -> None: ...
def load_global_variables() -> None: ...
def parse(value: str) -> MathStructure: ...
def set_global_evaluation_options(options: EvaluationOptions) -> None: ...
def set_global_parse_options(options: ParseOptions) -> None: ...
def set_global_print_options(options: PrintOptions) -> None: ...
def set_global_sort_options(options: SortOptions) -> None: ...
def set_message_print_options(options: PrintOptions) -> None: ...
def set_precision(precision: int) -> None: ...

class Message:
    @property
    def text(self) -> str: ...
    @property
    def type(self) -> MessageType: ...

def take_messages() -> list[Message]: ...
