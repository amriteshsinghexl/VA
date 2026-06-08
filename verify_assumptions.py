"""Quick smoke-test for assumption_loader â€” run from abc_corp_va/"""
import sys
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

from loaders.assumption_loader import load_assumptions
from loaders.warnings import get_warnings

path = r"data\Assumptions_Extracted.xlsx"
print("Loading assumptions...")
assumptions = load_assumptions(path)
print(f"Sheets loaded: {len(assumptions)}")

checks = [
    "VM21CA_LapsePAD_Scalar",
    "VM21PA_BaseLapseRates_Non403b",
    "All_i4L_MortalityAgeShift",
    "VM21CA_AnnuityCertainFactor",
    "VM21CA_BaseMortality_Single",
    "NYREG213_DynLapse_LifeFactors_M",
    "VM21PA_PerPolicyExpenses",
    "VM21CA_PM_BaseLapseRates",
]

for name in checks:
    if name not in assumptions:
        print(f"\n{name}: NOT FOUND")
        continue
    df = assumptions[name]
    meta = df.attrs.get("meta", {})
    print(f"\n{name}:")
    print(f"  shape={df.shape}")
    print(f"  index name={df.index.name!r}  first 3 idx vals={df.index[:3].tolist()}")
    print(f"  cols (first 6)={list(df.columns)[:6]}")
    src = meta.get('source_range', 'N/A')
    print(f"  source_range={src}")
    if not df.empty and len(df.columns) > 0:
        row0 = df.iloc[0]
        print(f"  row[0] first 4 values: {row0.iloc[:4].tolist()}")

w_all = get_warnings()
dummy_w = [w for w in w_all if "placeholder" in w.message.lower() or "dummy" in w.message.lower()]
count_w = [w for w in w_all if "Expected 72" in w.message]
print(f"\nTotal warnings: {len(w_all)}")
print(f"  DUMMY placeholder warnings: {len(dummy_w)}")
print(f"  Sheet-count warnings: {len(count_w)}")
if count_w:
    print(f"  -> {count_w[0].message}")

# Verify specific expected values
print("\n--- Value spot-checks ---")

# VM21CA_LapsePAD_Scalar: Gross and Net scalars should be 2.07 for first row
lp = assumptions.get("VM21CA_LapsePAD_Scalar")
if lp is not None and not lp.empty:
    try:
        # Try to find the 2.07 value
        vals = lp.values.flatten()
        vals = [v for v in vals if v is not None and str(v) != "nan"]
        print(f"VM21CA_LapsePAD_Scalar values: {vals[:6]}")
    except Exception as e:
        print(f"VM21CA_LapsePAD_Scalar error: {e}")

# VM21CA_AnnuityCertainFactor: first value should be 0.034
acf = assumptions.get("VM21CA_AnnuityCertainFactor")
if acf is not None and not acf.empty:
    try:
        r0 = acf.iloc[0]
        print(f"VM21CA_AnnuityCertainFactor row[0]: {r0.to_dict()}")
    except Exception as e:
        print(f"VM21CA_AnnuityCertainFactor error: {e}")

print("\nDone.")
