# Phase 6 Community Cloud activation

The public Streamlit deployment uses the repository's `main` branch and `app.py` entrypoint. Streamlit Community Cloud installs `requirements.txt` in a Python 3.12 environment and serves the app on its managed `streamlit.app` domain.

## Deployment settings

- Repository: `ccooper-data/black-outcomes-intelligence`
- Branch: `main`
- Entry point: `app.py`
- Python: `3.12`

Deploy first without secrets. The deterministic dashboard should render while Ask the Data shows its disabled state.

## Server-side secrets

Configure the following as root-level secrets in the app's Advanced settings. Never commit a `.streamlit/secrets.toml` file or paste the key into an issue, pull request, workflow log, or chat.

```toml
OPENAI_API_KEY = "<service-account key entered directly in Streamlit>"
OPENAI_MODEL = "gpt-6-luna"
ASK_DATA_ENABLED = "false"
```

Root-level Streamlit secrets are exposed to the application as environment variables. Keep `ASK_DATA_ENABLED` false during the private smoke test. Change it to `true` only after explicit approval.

## OpenAI project controls

Use a dedicated production project and service account. Set a $10 monthly hard project limit and a lower spend alert before creating live traffic. Confirm that the configured model is available to the service-account key.

## Smoke test and activation

1. Confirm the dashboard loads without AWS credentials.
2. Confirm chat is visibly disabled with the initial settings.
3. Add the service-account key while leaving `ASK_DATA_ENABLED=false`.
4. Temporarily enable chat for a controlled test and ask one supported aggregate question.
5. Test a suppressed-data request and an unsupported city-level request.
6. Confirm citations and the evidence expander match the answer.
7. Check OpenAI project usage, then return chat to disabled if final public approval has not been given.
8. After explicit approval, set `ASK_DATA_ENABLED=true` and monitor project usage and errors.

The in-app five-requests-per-minute and 25-requests-per-session limits are defense in depth, not a substitute for the OpenAI project hard limit. A visitor can create a new browser session.
