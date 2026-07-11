# 0214 live skill smoke

Date: 2026-07-04

Yoke now live-smokes folder skills on both v1 default surfaces:

- Codex app-server: `scripts/smoke_harnesses.py --surface codex:app --run-codex-app-skills` returned `yoke-codex-skill-smoke`.
- Claude Python SDK: `scripts/smoke_harnesses.py --surface claude:sdk --run-claude-skills` returned `yoke-claude-skill-smoke`.

The Claude fix has two parts:

- Plugin-backed Claude skills are exposed as `plugin-name:skill-name`, so Yoke path skills lower to namespaced skill selectors when the skill path belongs to a Claude local plugin root.
- Claude requires the `Skill` tool when Yoke passes an explicit `tools` list and `skills` is set, so the Claude adapter adds `Skill` whenever skills are enabled.

Codex app-server remains un-namespaced for the smoke prompt because Yoke passes native extra skill roots to the app-server surface.
