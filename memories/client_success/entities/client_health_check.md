# Client Health Check Framework
- frequency: Monthly for strategic accounts, quarterly for others
- data_sources:
  - product_usage: Mode → Usage/Seat Adoption Dashboard
  - support_tickets: Zendesk → Enterprise Queue
  - sentiment: Executive sponsor survey (Typeform)
  - financials: NetSuite → ARR Movements report
- scoring:
  - usage: 0-3 scale (0 = dormant, 3 = >80% active seats)
  - sentiment: 0-3 scale (0 = detractor, 3 = promoter)
  - value_realization: 0-2 scale (0 = unclear ROI, 2 = quantified outcomes)
  - risk_flags: subtract 1 per open SEV-1/2 escalation
- workflow:
  1. Extract metrics via Mode snapshot (Monday 08:00)
  2. Populate health template in Notion for each account
  3. Review with Account Team during mid-week standup
  4. Assign mitigation owners for any score ≤1
- automation:
  - Slack bot posts weekly adoption deltas to #client-success-war-room
  - Gainsight sync publishes health score to CRM nightly
- references:
  - Health score rubric: Google Drive → Success/Health Rubric.pdf
  - Renewal risk response kit: [[entities/renewal_strategy.md]]
