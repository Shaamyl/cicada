from collections import ChainMap
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from cicada.api.domain.triggers import Trigger
from cicada.ast.common import trigger_to_record
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    BooleanValue,
    FileNode,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    MemberExpression,
    NodeVisitor,
    NumericExpression,
    NumericValue,
    OnStatement,
    ParenthesisExpression,
    RecordValue,
    StringExpression,
    StringValue,
    UnaryExpression,
    UnaryOperator,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.ast.types import RecordType


class ConstexprEvalVisitor(NodeVisitor[Value]):
    """
    The constexpr visitor is a visitor which only evaluates expressions which
    are constant expressions. This is primarily for effeciency and safety:
    effeciency in that it allows for pre-evaluating semanticly sound AST trees
    without spinning up a sandboxed environment to run them, and safety in that
    you can evaluate an AST tree using this visitor and be sure that no bad
    things happen (arbitrary shell commands, etc).
    """

    symbols: ChainMap[str, Value]
    trigger: Trigger | None

    def __init__(self, trigger: Trigger | None = None) -> None:
        self.symbols = ChainMap()
        self.trigger = trigger

        if trigger:
            event = cast(RecordValue, trigger_to_record(trigger))
            self.symbols["event"] = event

            # TODO: make function for doing this
            env = RecordValue(
                cast(RecordValue, event.value["env"]).value,
                [
                    x
                    for x in cast(RecordType, event.type).fields
                    if x.name == "env"
                ][0].type,
            )

            self.symbols["env"] = env

    def visit_file_node(self, node: FileNode) -> Value:
        for expr in node.exprs:
            match expr.accept(self):
                case UnreachableValue():
                    break

        return UnitValue()

    def visit_member_expr(self, node: MemberExpression) -> Value:
        match node:
            case MemberExpression(
                lhs=IdentifierExpression(name=lhs_name), name=name
            ):
                lhs = self.symbols[lhs_name]

                if isinstance(lhs, RecordValue):
                    return lhs.value[name]

        raise NotImplementedError()

    def visit_let_expr(self, node: LetExpression) -> Value:
        expr = node.expr.accept(self)

        self.symbols[node.name] = expr

        return expr

    def visit_ident_expr(self, node: IdentifierExpression) -> Value:
        return self.symbols[node.name]

    def visit_paren_expr(self, node: ParenthesisExpression) -> Value:
        return node.expr.accept(self)

    def visit_num_expr(self, node: NumericExpression) -> Value:
        return node

    def visit_str_expr(self, node: StringExpression) -> Value:
        return node

    def visit_bool_expr(self, node: BooleanExpression) -> Value:
        return node

    def visit_unary_expr(self, node: UnaryExpression) -> Value:
        if node.oper == UnaryOperator.NOT:
            rhs = node.rhs.accept(self)

            assert isinstance(rhs, BooleanValue)

            return BooleanValue(not rhs.value)

        if node.oper == UnaryOperator.NEGATE:
            rhs = node.rhs.accept(self)

            assert isinstance(rhs, NumericValue)

            return NumericValue(-rhs.value)

        raise NotImplementedError()

    def visit_binary_expr(self, node: BinaryExpression) -> Value:
        # TODO: simplify

        lhs = node.lhs.accept(self)
        rhs = node.rhs.accept(self)

        if node.oper == BinaryOperator.IS:
            try:
                return BooleanValue(lhs.value == rhs.value)  # type: ignore

            except TypeError as ex:  # pragma: no cover
                raise NotImplementedError() from ex

        if isinstance(lhs, StringValue) and isinstance(rhs, StringValue):
            if node.oper == BinaryOperator.ADD:
                return StringValue(lhs.value + rhs.value)

        elif isinstance(lhs, NumericValue) and isinstance(rhs, NumericValue):
            if node.oper == BinaryOperator.EXPONENT:
                return NumericValue(lhs.value**rhs.value)

            if node.oper == BinaryOperator.ADD:
                return NumericValue(lhs.value + rhs.value)

            if node.oper == BinaryOperator.SUBTRACT:
                return NumericValue(lhs.value - rhs.value)

            if node.oper == BinaryOperator.MULTIPLY:
                return NumericValue(lhs.value * rhs.value)

            if node.oper == BinaryOperator.DIVIDE:
                # TODO: move this to semantic layer
                return NumericValue(int(lhs.value / rhs.value))

            if node.oper == BinaryOperator.MODULUS:
                return NumericValue(lhs.value % rhs.value)

            if node.oper == BinaryOperator.AND:
                return NumericValue(lhs.value & rhs.value)

            if node.oper == BinaryOperator.OR:
                return NumericValue(lhs.value | rhs.value)

            if node.oper == BinaryOperator.XOR:
                return NumericValue(lhs.value ^ rhs.value)

            if node.oper == BinaryOperator.LESS_THAN:
                return BooleanValue(lhs.value < rhs.value)

            if node.oper == BinaryOperator.GREATER_THAN:
                return BooleanValue(lhs.value > rhs.value)

        elif isinstance(lhs, BooleanValue) and isinstance(rhs, BooleanValue):
            if node.oper == BinaryOperator.AND:
                return BooleanValue(lhs.value and rhs.value)

            if node.oper == BinaryOperator.OR:
                return BooleanValue(lhs.value or rhs.value)

            if node.oper == BinaryOperator.XOR:
                return BooleanValue(lhs.value ^ rhs.value)

        raise NotImplementedError()

    def visit_on_stmt(self, node: OnStatement) -> Value:
        assert self.trigger

        if node.event != self.trigger.type:
            return UnreachableValue()

        if node.where:
            should_run = node.where.accept(self)

            if isinstance(should_run, BooleanValue) and should_run.value:
                return should_run

            return UnreachableValue()

        return BooleanValue(True)

    def visit_if_expr(self, node: IfExpression) -> Value:
        with self.new_scope():
            cond = node.condition.accept(self)

            assert isinstance(cond, BooleanValue | NumericValue | StringValue)

            if cond.value:
                return node.body.accept(self)

            return UnitValue()

    def visit_block_expr(self, node: BlockExpression) -> Value:
        last: Value = UnitValue()

        for expr in node.exprs:
            last = expr.accept(self)

        return last

    @contextmanager
    def new_scope(self) -> Iterator[None]:
        self.symbols = self.symbols.new_child()

        yield

        self.symbols = self.symbols.parents
