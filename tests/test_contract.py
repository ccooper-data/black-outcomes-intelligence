import pandas as pd
from src.transform.build_marts import validate

def test_valid_contract():
    df=pd.DataFrame({"SEX_LABEL":["Black women"],"AGE_BAND":["30-34"],"MARITAL_STATUS":["Married"],"PWGTP":[10]})
    validate(df)
