import pandas as pd
from src.transform.build_marts import validate

def test_valid_contract():
    df=pd.DataFrame({"STATE":[1],"AGEP":[30],"RAC1P":[2],"MAR":[1],"SCHL":[21],"PINCP":[50000],"PWGTP":[10]})
    validate(df)
