import re

class FilterExpression:
    def __init__(self, attr, operator, value):
        self.attr = attr
        self.operator = operator
        self.value = value

    def __str__(self):
        return f"{self.attr} {self.operator} {repr(self.value)}"

    def __and__(self, other):
        return CombinedExpression(self, other, op='AND')

    def __or__(self, other):
        return CombinedExpression(self, other, op='OR')

    def match(self, obj):
        node_value = getattr(obj, self.attr)
        if self.operator == '=':
            if isinstance(self.value, str) and len(self.value) > 2 and self.value.startswith('/') and self.value.endswith('/'):
                pattern = self.value[1:-1]        
                return re.fullmatch(pattern, str(node_value)) is not None
            return node_value == self.value
        elif self.operator == '!=':
            if isinstance(self.value, str) and len(self.value) > 2 and self.value.startswith('/') and self.value.endswith('/'):
                pattern = self.value[1:-1]
                return re.fullmatch(pattern, str(node_value)) is None
            return node_value != self.value
        elif self.operator == '>':
            return node_value > self.value
        elif self.operator == '>=':
            return node_value >= self.value
        elif self.operator == '<':
            return node_value < self.value
        elif self.operator == '<=':
            return node_value <= self.value
        return False
    
    def as_alternatives(self):
        return [self]

class CombinedExpression:
    def __init__(self, *expressions, op=None):
        if op is None:
            raise ValueError("Operator (op) must be provided")
        self.op = op
        self.expressions = []
        for expr in expressions:
            if isinstance(expr, CombinedExpression) and expr.op == op:
                self.expressions.extend(expr.expressions)
            else:
                self.expressions.append(expr)

    def __str__(self):
        return f"({f' {self.op} '.join(str(e) for e in self.expressions)})"

    def __and__(self, other):
        return CombinedExpression(self, other, op='AND')

    def __or__(self, other):
        return CombinedExpression(self, other, op='OR')

    def match(self, obj):
        if self.op == 'AND':
            return all(expr.match(obj) for expr in self.expressions)
        elif self.op == 'OR':
            return any(expr.match(obj) for expr in self.expressions)
        return expr.match(obj)

    def as_alternatives(self):
        """
        Return a list of all alternative matchningsuttryck (filter expressions or AND-groups) in this CombinedExpression.
        If this is an OR-expression, returns all sub-expressions as alternatives.
        If this is an AND-expression, returns [self] (since all must match together).
        """
        if self.op == 'OR':
            result = []
            for expr in self.expressions:
                if isinstance(expr, CombinedExpression) and expr.op == 'OR':
                    result.extend(expr.as_alternatives())
                else:
                    result.append(expr)
            return result
        else:
            return [self]

class FilterAttribute:

    def __init__(self, attribute_name: str):
        self.attr_name = attribute_name
    
    def eq(self, value):
        return FilterExpression(self.attr_name, '=', value)

    def ne(self, value):
        return FilterExpression(self.attr_name, '!=', value)

    def gt(self, value):
        return FilterExpression(self.attr_name, '>', value)

    def gte(self, value):
        return FilterExpression(self.attr_name, '>=', value)

    def lt(self, value):
        return FilterExpression(self.attr_name, '<', value)

    def lte(self, value):
        return FilterExpression(self.attr_name, '<=', value)

    def __eq__(self, value): return self.eq(value)
    def __ne__(self, value): return self.ne(value)
    def __gt__(self, value): return self.gt(value)
    def __ge__(self, value): return self.gte(value)
    def __lt__(self, value): return self.lt(value)
    def __le__(self, value): return self.lte(value)