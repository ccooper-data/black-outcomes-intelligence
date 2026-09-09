from pathlib import Path
import pandas as pd

REQUIRED = {"SEX_LABEL", "AGE_BAND", "MARITAL_STATUS", "PWGTP"}

def validate(df: pd.DataFrame) -> None:
    missing = REQUIRED - set(df.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    if (df.PWGTP <= 0).any(): raise ValueError("PWGTP must be positive")

def weighted_rate(g, flag):
    return (g[flag] * g.PWGTP).sum() / g.PWGTP.sum()

def build_age_sex(df):
    validate(df)
    df = df.copy()
    df["is_married"] = df.MARITAL_STATUS.eq("Married").astype(int)
    df["is_never_married"] = df.MARITAL_STATUS.eq("Never married").astype(int)
    rows=[]
    for keys,g in df.groupby(["SEX_LABEL","AGE_BAND"], observed=True):
        rows.append({"sex":keys[0],"age_band":keys[1],"sample_n":len(g),
                     "weighted_population":g.PWGTP.sum(),
                     "married_rate":weighted_rate(g,"is_married"),
                     "never_married_rate":weighted_rate(g,"is_never_married")})
    return pd.DataFrame(rows)
