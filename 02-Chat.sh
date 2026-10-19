#!/usr/bin/env bash
# 02 - Chat mode
#
# Builds on 01-LLM-Call.sh. Two changes:
#   1. The curl call moves into a function, call_llm, that takes the
#      conversation (a JSON array of messages) and returns the API response.
#   2. A loop around it: read a line from the user, append it to the
#      conversation, call the LLM, append the reply, print it, repeat.
#
# The conversation lives in a single shell variable, MESSAGES, holding a JSON
# array. jq does all the JSON building so we never hand-escape strings.

set -euo pipefail
source .env

MODEL="openai/gpt-6-luna"
MESSAGES='[]'

# call_llm <messages-json>  ->  prints the raw API response JSON
call_llm() {
  local messages="$1"
  local body
  body=$(jq -n --arg model "$MODEL" --argjson messages "$messages" \
    '{model: $model, max_tokens: 1500, messages: $messages}')

  curl -s https://openrouter.ai/api/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -d "$body"
}

# add_message <role> <content>  ->  appends to MESSAGES
add_message() {
  MESSAGES=$(jq --arg role "$1" --arg content "$2" \
    '. + [{role: $role, content: $content}]' <<<"$MESSAGES")
}

echo "Chat with $MODEL. Empty line or Ctrl-D to quit."
while true; do
  IFS= read -e -r -p "you> " input || break
  [ -z "$input" ] && break

  add_message user "$input"

  response=$(call_llm "$MESSAGES")
  reply=$(jq -r '.choices[0].message.content // (.error.message | "ERROR: " + .)' <<<"$response")

  add_message assistant "$reply"
  #jq . <<<"$MESSAGES" >&2
  printf 'llm> %s\n\n' "$reply"
done
