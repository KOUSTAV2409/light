# Real-user validation workflow

Light is not ready for paid features until real usage is measured with consent.

## Enable local metrics (opt-in)

In `~/.config/light/configuration.json`:

```json
"usage_metrics_enabled": true
```

Or use **Tray → Preferences → Enable privacy-safe local usage metrics**.

Then use Light normally for at least 2–4 weeks.

## Review local summary

```bash
./run.sh metrics
```

This reads `~/.local/share/light/usage_metrics.json` and prints aggregate counts only.

## What is recorded

- launch count
- search count
- activate_result count
- active day count

## What is never recorded

- search queries
- file paths
- clipboard contents
- AI answer text
- API keys
- URLs opened

## Validation gates before paid features

See `PAID_FEATURES.md`. Minimum bar:

1. 4+ weeks of opt-in metrics from consenting testers
2. Week-one and week-four retention from the same cohort
3. Interviews showing repeated value from one advanced feature
4. Free tier remains useful without payment
5. Privacy, refund, and account-deletion policies published

## Suggested tester script

Ask 5–10 Linux users to:

1. Install Light (`.deb` or `./run.sh`)
2. Enable metrics in Preferences
3. Use Light daily for launcher, file search, and AI fact queries
4. Share `./run.sh metrics` output weekly (screenshot is fine)
5. Answer: “Would you miss this if it disappeared tomorrow?”

Do not enable billing until those gates are met.
