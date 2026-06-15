"""
AST-based formula extractor for VA model calculation modules.

Parses Python source files using the built-in `ast` module and extracts the
right-hand-side expression for each named variable assignment.  The extracted
expressions are converted to Excel formula notation with [col_name] placeholders
that the writer resolves to concrete cell addresses at write time.

Usage
-----
    extractor = FormulaExtractor("cashflows/interest.py")
    formulas  = extractor.extract({"i_aey", "i_monthly", "disc_factor"})
    # {"i_aey": "((1.0 + ([i_bey] / 2.0))^2 - 1.0)", ...}
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Optional, Set

ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Python AST → Excel formula string translator
# ---------------------------------------------------------------------------

class _Translator:
    """Translate a single Python AST expression node to an Excel formula string.

    Column-name references are wrapped in [brackets] so the caller can
    substitute them with concrete cell addresses later.
    """

    _BINOP: Dict[type, str] = {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^",
    }
    _CMPOP: Dict[type, str] = {
        ast.Eq: "=", ast.NotEq: "<>", ast.Lt: "<", ast.LtE: "<=",
        ast.Gt: ">",  ast.GtE: ">=",
    }
    _BUILTINS: Dict[str, str] = {
        "max": "MAX", "min": "MIN", "abs": "ABS", "sum": "SUM",
    }
    _NP_FUNCS: Dict[str, str] = {
        "maximum": "MAX", "minimum": "MIN", "exp": "EXP",
        "sqrt": "SQRT", "log": "LN",
    }

    def __init__(self, known_cols: Set[str]) -> None:
        self._cols = known_cols

    def tr(self, node: ast.expr) -> str:
        """Dispatch to the appropriate node translator."""
        m = getattr(self, f"_n_{type(node).__name__}", None)
        return m(node) if m else "..."

    # ---- node handlers ------------------------------------------------------

    def _n_BinOp(self, n: ast.BinOp) -> str:
        op = self._BINOP.get(type(n.op), "?")
        l, r = self.tr(n.left), self.tr(n.right)
        if isinstance(n.op, ast.Pow):
            return f"{l}^{r}"
        return f"({l} {op} {r})"

    def _n_UnaryOp(self, n: ast.UnaryOp) -> str:
        if isinstance(n.op, ast.USub):
            return f"-{self.tr(n.operand)}"
        return self.tr(n.operand)

    def _n_Constant(self, n: ast.Constant) -> str:
        return str(n.value)

    def _n_Num(self, n) -> str:          # Python 3.7 compat
        return str(n.n)

    def _n_Name(self, n: ast.Name) -> str:
        if n.id in self._cols:
            return f"[{n.id}]"
        # numpy/math module names — suppress
        if n.id in ("np", "math", "nan", "inf"):
            return "..."
        return n.id

    def _n_Subscript(self, n: ast.Subscript) -> str:
        # Pattern: arr[t] — treat as a reference to the 'arr' column
        if isinstance(n.value, ast.Name):
            name = n.value.id
            if name in self._cols:
                return f"[{name}]"
        return self.tr(n.value)

    def _n_Attribute(self, n: ast.Attribute) -> str:
        # np.nan, math.isnan → suppress
        return "..."

    def _n_Call(self, n: ast.Call) -> str:
        # Builtin names: max(), min(), abs()
        if isinstance(n.func, ast.Name):
            xl = self._BUILTINS.get(n.func.id.lower())
            if xl:
                args = ", ".join(self.tr(a) for a in n.args)
                return f"{xl}({args})"
        # numpy methods: np.maximum(), np.exp(), etc.
        if isinstance(n.func, ast.Attribute):
            xl = self._NP_FUNCS.get(n.func.attr.lower())
            if xl:
                args = ", ".join(self.tr(a) for a in n.args)
                return f"{xl}({args})"
        return "..."

    def _n_IfExp(self, n: ast.IfExp) -> str:
        t = self.tr(n.test)
        b = self.tr(n.body)
        o = self.tr(n.orelse)
        return f"IF({t}, {b}, {o})"

    def _n_Compare(self, n: ast.Compare) -> str:
        left = self.tr(n.left)
        parts = [left]
        for op, comp in zip(n.ops, n.comparators):
            parts.append(self._CMPOP.get(type(op), "?") + self.tr(comp))
        return "".join(parts)

    def _n_BoolOp(self, n: ast.BoolOp) -> str:
        fn = "AND" if isinstance(n.op, ast.And) else "OR"
        vals = ", ".join(self.tr(v) for v in n.values)
        return f"{fn}({vals})"

    def _n_Tuple(self, n: ast.Tuple) -> str:
        return "(" + ", ".join(self.tr(e) for e in n.elts) + ")"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FormulaExtractor:
    """
    Parse Python source files and extract variable-assignment formulas.

    The extracted formulas use [col_name] placeholders for column references
    and standard Excel operators/functions for arithmetic.
    """

    def __init__(self, *source_files: str) -> None:
        """
        Parameters
        ----------
        source_files
            File paths relative to the project root, or absolute paths.
        """
        self._files: list[Path] = []
        for f in source_files:
            p = Path(f)
            self._files.append(p if p.is_absolute() else ROOT / p)

    def extract(self, target_vars: Set[str]) -> Dict[str, str]:
        """
        Return {var_name: excel_formula_string} for all target_vars found.

        Scans all registered source files in order; later files override earlier
        ones if the same variable is assigned in multiple files.
        Only simple scalar or element-wise assignments are captured — loop
        bodies with complex branching produce "..." and are omitted.
        """
        translator = _Translator(known_cols=target_vars)
        result: Dict[str, str] = {}

        for src in self._files:
            if not src.exists():
                continue
            try:
                source = src.read_text(encoding="utf-8", errors="replace")
                tree   = ast.parse(source)
            except SyntaxError:
                continue
            result.update(self._scan(tree, target_vars, translator))

        return result

    # ---- internals ----------------------------------------------------------

    @staticmethod
    def _scan(
        tree: ast.Module,
        targets: Set[str],
        translator: _Translator,
    ) -> Dict[str, str]:
        found: Dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                name = _target_name(target)
                if name and name in targets:
                    formula = translator.tr(node.value)
                    if formula and formula != "...":
                        found[name] = formula
        return found


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _target_name(target: ast.expr) -> Optional[str]:
    """Extract the simple variable name from an assignment target, or None."""
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        return target.value.id
    return None
