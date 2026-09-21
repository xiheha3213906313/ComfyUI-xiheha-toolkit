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

## Three-level validation choice

When initialization, invalid configuration, or a model-binding mismatch
requires the user to choose among `simple`, `medium`, and `careful`, treat it as
a native structured-choice task:

1. Resolve and call the host's available user-input tool before considering a
   normal chat question.
2. If the tool supports options, present all three mutually exclusive choices
   in one question. Put `medium` first and mark it recommended, followed by
   `simple` and `careful`. Give each option one short impact description based
   on [validation-strategies.md](validation-strategies.md); do not hide a level,
   merge levels, or choose for the user.
3. State the saved level and configured/current model identities in the prompt
   when the choice was triggered by a model mismatch. During initialization,
   state that the choice becomes the project default and can later be changed
   or overridden for one task.
4. If the native UI can collect several independent decisions in one call, the
   validation choice may accompany project-parse consent as a separate field.
   Never bury the three levels inside another option or infer the validation
   choice from the parse answer.
5. If the tool cannot represent three choices but supports a waiting free-text
   response, ask for exactly one of the three names through that native UI. Do
   not truncate the list to satisfy a tool limit.
6. Continue only from an explicit answer that unambiguously maps to one level.
   Persist it before implementation when persistence is required. An empty,
   partial, timeout, cancellation, or closed prompt follows the fallback and
   stop rules in `SKILL.md`; it never authorizes the recommended default.

When plain-text fallback is required, explain the three choices concisely and
end the `final` response with one focused question asking the user to choose
`simple`, `medium`, or `careful`. End the turn immediately. Do not run a
command, persist `medium`, or begin implementation until the user replies.

After a tool is selected, follow the blocking-question and timeout rules in
`SKILL.md`. If several material choices cannot be resolved together, continue
in multiple rounds: wait for each answer before asking a dependent follow-up,
and do not implement from a partial answer. Dedicated permission or escalation
mechanisms always take priority over these normal decision tools.
