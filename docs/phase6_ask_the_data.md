# Phase 6: Ask the Data

Phase 6 adds an optional OpenAI-powered conversational layer to the Streamlit dashboard. It interprets only the repository's validated public aggregate snapshots. It does not query S3, AWS, ACS microdata, private Gold outputs, or person-level predictions.

## Evidence boundary

`src.ask_data.build_evidence_store` converts published national, state, intersectional, longitudinal, contrast, and aggregate model metrics into small citation-ready evidence records. Suppressed records retain only the public suppression status, reason, unweighted sample size, and weighted denominator; their estimates and uncertainty fields are already blank in the public snapshot and are never reconstructed.

Retrieval selects at most 16 relevant records for each question. The OpenAI request therefore contains the question, up to four recent session messages, and a bounded aggregate evidence packet. API response storage is disabled with `store=False`. Chat history remains in the user's Streamlit session and is limited to eight messages.

## Answer safeguards

The system instructions require evidence citations, forbid causal or individual claims, and prohibit calculation or invention. Application code then rejects an answer unless it cites supplied evidence IDs. It rejects any numeric token that does not appear in the evidence packet, and every numeric sentence must cite a record containing those exact numbers. A rejected answer is not displayed.

These controls reduce, but cannot eliminate, language-model error. The evidence expander shows every aggregate record supplied to the model so users can verify the answer. The deterministic dashboard remains the authoritative presentation.

## Configuration and cost controls

Set `OPENAI_API_KEY` only in the hosting platform's server-side secret store. Never commit it or accept it through a public dashboard input. The feature remains off unless `ASK_DATA_ENABLED=true` is also set, preventing an unrelated server key from activating public usage accidentally. `OPENAI_MODEL` is optional and defaults to `gpt-6-luna`; deployments can select another available model without code changes.

Requests are limited to 500 input characters, 500 output tokens, 16 evidence records, a 30-second timeout, and one retry. Each browser session is limited to five requests per minute and 25 total requests. For a public deployment, infrastructure-level quotas should supplement this session control because a user can create a new browser session. Development and CI use a fake client and make no paid API calls.

The integration uses the OpenAI Responses API. It is not the consumer ChatGPT website, and API usage is billed separately under the selected model's API pricing.
