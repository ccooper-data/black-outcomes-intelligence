# Black Outcomes Intelligence Platform

Production-oriented cloud analytics portfolio project using 2024 ACS PUMS microdata to study Black American adult marriage, education, income, employment, and related outcomes.

## Architecture
Census ACS PUMS -> Python ingestion/validation -> S3 Bronze -> curated Parquet/S3 Silver -> analytical marts/S3 Gold -> Glue Data Catalog -> Athena -> ML/API/BI.

## Engineering stack
Python, SQL, AWS S3, AWS Glue, Athena, Terraform, Docker, GitHub Actions. Planned: dbt, PySpark, XGBoost/SHAP, Streamlit/Power BI.

## Data integrity
Population estimates use ACS person weight PWGTP. Raw source data are not committed to Git.
