# User-input tool resolution

Read this reference immediately before asking a blocking user question. The
goal is to use the coding host's structured question UI when it is genuinely
available, without hallucinating a tool or ignoring mode restrictions.

## Known host mapping

| Coding agent | Preferred tool leaf name |
| --- | --- |
| Codex | `request_user_input` |
| Claude Code | `AskUserQuestion` |
| Antigravity | `ask_question` |
| Cursor | `AskQuestion` |
| GitHub Copilot | `ask_user` |
| OpenCode | `question` |
| workbuddy | `AskUserQuestion` |

Treat this table as a candidate map, not a guarantee. Tool availability,
namespace, schema, permissions, and allowed mode can differ by host version or
session. For example, a host may expose the mapped name but restrict it to a
planning mode.

## Resolution order

1. Determine the current coding-agent name from runtime/system context, host UI,
   or an explicit user statement. Do not infer it from the model name or model
   provider.
2. If the agent is known, look for the mapped leaf name in the tools actually
   exposed to the current turn. Accept namespaced forms when their final tool
   component matches exactly.
3. If exact matching fails, retry with case-insensitive and separator-insensitive
   matching of the mapped name and obvious host aliases. Never call a name that
   is not present in the live tool inventory.
4. If the agent is unknown or mapped matching still fails, search available or
   discoverable tool names and descriptions for a capability that asks the
   user for input, a decision, a question response, or human intervention and
   returns the answer to the current turn.
5. Reject permission/approval-only tools, notification tools, chat-message
   senders, and tools whose schema cannot represent the needed decision. When
   multiple candidates remain, prefer the structured tool that waits for and
   returns an explicit answer.
6. Verify the selected tool's current schema and mode restrictions before
   calling it. If it is unavailable, disallowed, ambiguous, or cannot express
   the decision safely, use the plain-text fallback from `SKILL.md`.

The `question_tool` object returned by `check_project_profile.py` provides the
configured/current agent, preferred candidate, and fallback action. It cannot
inspect the model's live tool inventory, so it never proves availability.

After a tool is selected, follow the blocking-question and timeout rules in
`SKILL.md`. If several material choices cannot be resolved together, continue
in multiple rounds: wait for each answer before asking a dependent follow-up,
and do not implement from a partial answer. Dedicated permission or escalation
mechanisms always take priority over these normal decision tools.
