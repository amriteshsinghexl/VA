"""
§2 — Model Configuration

Single source of truth for all run-time switches.
Populated by run.py from CLI arguments and then passed (read-only) to every module.
No module may mutate a Config after construction.

Configuration tab cell map:
  C3  = reserve_basis           C4  = reserve_method
  C5  = nyreg213_stdscn_num     C7  = partial_withdrawals
  C8  = projection_months       C10 = business_type
  C11 = gross_net (derived)     C19 = axis_scenario_length
  D3  = vm21_flag (derived convenience)
"""
from __future__ import annotations

import dataclasses
import warnings
from typing import Literal


ReserveBasis = Literal["VM21CA", "VM21PA", "NYREG213", "GAAPDAC", "CAPITAL"]
ReserveMethod = Literal["CARVM", "StdScn", "OptionValueFloor"]

# Basis pairs that are forbidden per TMD §2.5 reasonableness checks
_FORBIDDEN_COMBINATIONS: list[tuple[str, str]] = [
    # CARVM is a NYREG213 concept; VM21CA/VM21PA + CARVM produces nonsense
    ("VM21CA", "CARVM"),
    ("VM21PA", "CARVM"),
    ("GAAPDAC", "CARVM"),
    ("CAPITAL", "CARVM"),
]


@dataclasses.dataclass(frozen=True)
class Config:
    # ------------------------------------------------------------------ #
    # Paths                                                                #
    # ------------------------------------------------------------------ #
    policy_path: str
    assumptions_path: str
    output_dir: str

    # ------------------------------------------------------------------ #
    # Reserve switches  (Configuration!C3, C4)                            #
    # ------------------------------------------------------------------ #
    reserve_basis: ReserveBasis = "VM21PA"
    reserve_method: ReserveMethod = "StdScn"

    # ------------------------------------------------------------------ #
    # Configuration tab values                                             #
    # ------------------------------------------------------------------ #
    # C5 — NY REG 213 Std Scn number (1 or 2)
    nyreg213_stdscn_num: int = 1
    # C7 — partial withdrawals enabled (TRUE/FALSE)
    partial_withdrawals: bool = True
    # C8 — months of projection (default 480; max sensible = axis_scenario_length)
    projection_months: int = 480
    # C10 — business type: "D" = Direct, "A" = Assumed
    business_type: str = "D"
    # C19 — AXIS scenario length (controls scenario grid size)
    axis_scenario_length: int = 600

    # ------------------------------------------------------------------ #
    # Derived flags (computed in __post_init__, not constructor args)      #
    # ------------------------------------------------------------------ #

    # Configuration!D3: IF(OR(basis=VM21CA, basis=VM21PA), "VM21", basis)
    vm21_flag: str = dataclasses.field(init=False)

    # D-007: NYREG213 + CARVM → all charges suppressed to 0
    suppress_charges: bool = dataclasses.field(init=False)

    # D-006: CAPITAL basis → all lapses = 0
    capital_zero_lapse: bool = dataclasses.field(init=False)

    # D-008: NYREG213 + CARVM → Calc_Lapse_NYREG213 AL column = 0
    nyreg213_carvm_zero_lapse: bool = dataclasses.field(init=False)

    # Configuration!C11: IF(Company="LNL","Gross","Net")
    # Company is populated per-policy; this default matches LNL (direct business)
    gross_net: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        # frozen=True requires object.__setattr__ for derived fields

        vm21 = (
            "VM21"
            if self.reserve_basis in ("VM21CA", "VM21PA")
            else self.reserve_basis
        )
        object.__setattr__(self, "vm21_flag", vm21)

        object.__setattr__(
            self,
            "suppress_charges",
            self.reserve_basis == "NYREG213" and self.reserve_method == "CARVM",
        )
        object.__setattr__(
            self,
            "capital_zero_lapse",
            self.reserve_basis == "CAPITAL",
        )
        object.__setattr__(
            self,
            "nyreg213_carvm_zero_lapse",
            self.reserve_basis == "NYREG213" and self.reserve_method == "CARVM",
        )
        # gross_net defaults to "Gross" (LNL direct); overridden by orchestrator
        # once policy company is known (LNY → "Net")
        object.__setattr__(self, "gross_net", "Gross")

        # ---- reasonableness warnings (TMD §2.5) -------------------------
        combo = (self.reserve_basis, self.reserve_method)
        if combo in _FORBIDDEN_COMBINATIONS:
            warnings.warn(
                f"Config: reserve_basis={self.reserve_basis} + "
                f"reserve_method={self.reserve_method} is nonsensical "
                f"(CARVM is a NYREG213-only concept). Results will be invalid.",
                UserWarning,
                stacklevel=2,
            )

        if self.projection_months > self.axis_scenario_length:
            warnings.warn(
                f"Config: projection_months={self.projection_months} exceeds "
                f"axis_scenario_length={self.axis_scenario_length}. "
                f"Months {self.axis_scenario_length + 1}–{self.projection_months} "
                f"will have no scenario data; fund returns will be 0.",
                UserWarning,
                stacklevel=2,
            )

    def with_gross_net(self, gross_net: str) -> "Config":
        """Return a new Config with gross_net updated (used by orchestrator)."""
        d = dataclasses.asdict(self)
        # remove derived fields before reconstructing
        for key in ("vm21_flag", "suppress_charges", "capital_zero_lapse",
                    "nyreg213_carvm_zero_lapse", "gross_net"):
            d.pop(key, None)
        new = Config(**d)
        object.__setattr__(new, "gross_net", gross_net)
        return new
