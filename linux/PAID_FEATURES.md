# Paid-feature release gate

Light currently contains no billing SDK, paywall, account requirement, or
paid-feature restriction.

Do not introduce paid features until all of these are supported by real data:

1. At least four weeks of opt-in active-user measurements.
2. Week-one and week-four retention cohorts from consenting testers.
3. User interviews showing repeated value from a specific advanced feature.
4. A free tier that keeps application search, file search, calculator, actions,
   clipboard history, and bring-your-own-key AI useful.
5. Published privacy, data retention, refund, and account deletion policies.

When those gates are met, the first candidate should be an optional hosted-AI
plan. BYOK and all local launcher functions should remain free. Entitlements
must be checked behind a single service boundary; search providers and the UI
must not contain direct payment-provider logic.
