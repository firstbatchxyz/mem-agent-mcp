# Oncology Memory Console

This workspace captures multi-source patient context for a synthetic care team. Mem-agent may read and write within this directory to coordinate clinical notes, behavioral insights, wearable summaries, and care plans. All information is fictional, generated for demonstration purposes.

## Available Patients
- [[entities/patients/sanjay_patel.md|Sanjay Patel]] — Type 2 diabetes (risk: Medium)
- [[entities/patients/linda_chan.md|Linda Chan]] — Triple-negative breast cancer (risk: High)
- [[entities/patients/james_rivera.md|James Rivera]] — Metastatic colorectal cancer (risk: High)
- [[entities/patients/victor_nguyen.md|Victor Nguyen]] — Chronic kidney disease (risk: High)
- [[entities/patients/malik_abiola.md|Malik Abiola]] — Resistant hypertension (risk: Medium)

## Usage Guidance
- Always request filters when sharing information with external parties.
- Prefer multi-hop reasoning: review assessments, behavior, and wearable notes together before concluding.
- Update assessments via Python tools to keep structured history consistent.

## Handy Links
- [[entities/clinic/care_team.md|Care Team Directory]]
- [[entities/clinic/redaction_protocol.md|Redaction Protocol]]
