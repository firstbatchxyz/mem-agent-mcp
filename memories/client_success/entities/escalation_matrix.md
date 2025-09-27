# Escalation Matrix
- objective: Ensure rapid response for enterprise issues impacting retention or adoption
- severity_levels:
  - sev1:
      criteria: Production outage or security incident
      response_time: 30 minutes
      on_call: Duty Manager (week 12 = Priya Singh)
      notify: CTO, Head of Security, Account Executive, CEO sponsor
      channels: PagerDuty bridge + Slack #incident-room
  - sev2:
      criteria: Core workflow degradation, data delay >24h
      response_time: 2 hours
      on_call: Senior CSM + Support Escalations
      notify: Team Lead [[entities/team_lead.md]], product owner
      channels: Slack thread + Zoom war room
  - sev3:
      criteria: Feature gaps or minor SLA miss
      response_time: 1 business day
      owner: Assigned CSM
      notify: Account Manager
      channels: Salesforce case + weekly call
- process:
  1. Log incident in Gainsight Escalation object
  2. Post summary in Slack template (severity, impact, ETA)
  3. Hold daily client sync until resolved (sev1/sev2)
  4. Conduct retro within 5 business days
- weekend_coverage:
  - Duty Manager rotation doc: Notion → Operations/Duty Manager Roster
  - If unreachable within 20 minutes escalate directly to VP Success (vp.success@example.com)
