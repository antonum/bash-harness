#!/usr/bin/env bash
# 03 - The harness
#
# Builds on 02-Chat.sh. The model can now run shell commands. Four changes:
#   1. TOOLS: a JSON schema describing one tool, "bash", with a single
#      "command" argument. It is sent with every request.
#   2. add_message now takes jq arguments plus an object expression, so one
#      function appends any message shape: user text, the assistant reply
#      verbatim (tool_calls included), or a tool result.
#   3. run_tool: executes the command the model asked for and captures the
#      output (stdout + stderr + exit code) as a string.
#   4. The agent loop: after each LLM reply, if it contains tool_calls we run
#      them, append the results as "tool" messages, and call the LLM again.
#      Only when a reply has no tool_calls do we print it and go back to the
#      user. That inner loop is the whole "agent".
#
# Big payloads go through stdin, never the command line: curl reads the
# request body with -d @- and jq reads tool output with --rawfile. The
# conversation is resent in full on every call and only grows, and a single
# `cat` of a big file would otherwise hit ARG_MAX (1 MB on macOS).
#
# WARNING: this runs whatever the model asks for, with your permissions.
# It is a tutorial. Read the commands as they scroll by.

set -euo pipefail
source .env

MODEL="openai/gpt-6-luna"
SYSTEM_PROMPT="You are a helpful assistant running on the user's machine. Use the bash tool to inspect files, run programs, and answer questions about the system. Prefer running a command over guessing."

TOOLS='[{
  "type": "function",
  "function": {
    "name": "bash",
    "description": "Run a bash command on the user'"'"'s machine and return its stdout, stderr and exit code.",
    "parameters": {
      "type": "object",
      "properties": { "command": { "type": "string", "description": "The command to run." } },
      "required": ["command"]
    }
  }
}]'

# call_llm <messages-json>  ->  raw API response. The request body is built by
# jq and piped straight into curl; it never becomes a shell variable.
call_llm() {
  jq -n --arg model "$MODEL" --argjson messages "$1" --argjson tools "$TOOLS" \
    '{model: $model, max_tokens: 8000, messages: $messages, tools: $tools}' |
  curl -sS https://openrouter.ai/api/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -d @-
}

# add_message [jq args...] <jq-object>  ->  appends one message to MESSAGES.
# The call site spells out the exact JSON shape of the message it adds.
add_message() {
  MESSAGES=$(jq --argjson m "$(jq -nc "$@")" '. + [$m]' <<<"$MESSAGES")
}

# run_tool <command>  ->  combined output plus the exit code
run_tool() {
  local output status=0
  output=$(bash -c "$1" 2>&1) || status=$?
  printf '%s\n[exit code: %d]' "$output" "$status"
}

MESSAGES='[]'
add_message --arg c "$SYSTEM_PROMPT" '{role: "system", content: $c}'

echo "Agent with bash tool ($MODEL). Empty line or Ctrl-D to quit."
while IFS= read -e -r -p "you> " input && [ -n "$input" ]; do
  add_message --arg c "$input" '{role: "user", content: $c}'

  # Agent loop: keep calling the LLM until it stops asking for tools.
  while true; do
    ( SECONDS=0; while sleep 1; do printf '\rthinking %ds' "$SECONDS"; done ) & disown
    response=$(call_llm "$MESSAGES"); kill $!; printf '\r\033[K'
    message=$(jq -ce '.choices[0].message' <<<"$response") ||
      { printf 'ERROR: %s\n\n' "$(jq -r '.error.message // .' <<<"$response")"; break; }

    add_message --argjson m "$message" '$m'   # echo it back verbatim, tool_calls and all

    if ! jq -e '.tool_calls | length > 0' <<<"$message" >/dev/null; then
      printf 'llm> %s\n\n' "$(jq -r '.content' <<<"$message")"
      break
    fi

    # One tool call per line; run each and feed the result back.
    while IFS= read -r call; do
      call_id=$(jq -r '.id' <<<"$call")
      # arguments is a JSON string; a reply cut off by max_tokens leaves it unparseable.
      command=$(jq -r '.function.arguments | try (fromjson | .command) catch empty' <<<"$call")
      if [ -z "$command" ]; then
        result="ERROR: tool call arguments were not valid JSON; the reply was probably cut off. Use shorter commands, e.g. write large files in several appends."
      else
        printf 'bash> %s\n' "$command"
        result=$(run_tool "$command")
        printf '%s\n' "$result" | sed 's/^/      /'
      fi
      add_message --arg id "$call_id" --rawfile c <(printf '%s' "$result") \
        '{role: "tool", tool_call_id: $id, content: $c}'
    done < <(jq -c '.tool_calls[]' <<<"$message")
  done
done
