# Minimalistic AI Harness in 62 lines of bash script

In this article we'll build a minimalistic AI harness step by step from simple individual LLM call to chatbot to coding agent capable of building the game like tetris. Using nothing but Bash script.

What you'll need:
- Access to LLM. I'm using OpenAI's LLM via OpenRouter here. But you can use any other modern LLM capable of tool calling either locally or remotely
- API_KEY for your LLM provider
- Computer with the terminal, bash, curl, jq

## Step 1. Calling the LLM

The very first thing we need to do is to be able to call LLM from bash. See `01-LLM-Call.sh`.

```bash
OPENROUTER_API_KEY="sk-or-v1-12345....."

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -d '{
  "model": "openai/gpt-6-luna",
  "max_tokens": 1500,
  "messages": [
    {
      "role": "user",
      "content": "In one sentence, what is jq?"
    }
  ]
}'
```

Simply running this code in the terminal should generate a blob of JSON. Somewhere inside it is the LLM's answer.

It's a bit easier to read if you parse the output with jq, just piping the results to `jq .`

```bash
bash 01-LLM-Call.sh | jq .
```

```json
{
  "id": "gen-1792430673-n7TeT6PuaQl4j2fmQhpj",
  "object": "chat.completion",
  "created": 1792430673,
  "model": "openai/gpt-6-luna",
  "provider": "OpenAI",
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "jq is a lightweight command-line tool for querying, transforming, and formatting JSON data.",
        "refusal": null,
        "reasoning": null,
        "reasoning_details": [ ... ]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 14,
    "completion_tokens": 21,
    "total_tokens": 35,
    ...
  }
}
```

Or if you want to extract just the response text from this JSON, again, use jq:

```bash
bash 01-LLM-Call.sh | jq '.choices[0].message.content'

"jq is a lightweight command-line tool for querying, transforming, and formatting JSON data."
```

So far so good. We can call LLM from bash script using curl, LLM responds with JSON and we can parse the results with jq. The model just described jq for us, and we'll be using it a lot down the road.

One important thing to note here: each LLM call is completely "stateless". LLM has no idea what previos questions you have asked and what did it answer yesterday or a few seconds ago. It would always respond only based on the context of the current request, its own knowledge and nothing else. Adding the right context (chat history), giving LLM tools to execute (read/write files) etc. is the responcibility of the harness.

Harness is what we going to build in the next two steps. Let's go!

## Step 2. Chat loop

To turn a single call into a chat we need exactly two things: remember what was said, and loop. See `02-Chat.sh`.

The conversation is just a JSON array of messages in a shell variable. We never hand-write JSON, jq builds it for us:

```bash
MESSAGES='[]'

add_message() {
  MESSAGES=$(jq --arg role "$1" --arg content "$2" \
    '. + [{role: $role, content: $content}]' <<<"$MESSAGES")
}
```

The curl call from step 1 moves into a function that takes the whole array and sends it as `messages`:

```bash
call_llm() {
  local body
  body=$(jq -n --arg model "$MODEL" --argjson messages "$1" \
    '{model: $model, max_tokens: 1500, messages: $messages}')

  curl -s https://openrouter.ai/api/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -d "$body"
}
```

And the loop: read a line, append it as `user`, call the LLM, append the reply as `assistant`, print it, repeat.

```bash
while true; do
  IFS= read -e -r -p "you> " input || break
  [ -z "$input" ] && break

  add_message user "$input"
  response=$(call_llm "$MESSAGES")
  reply=$(jq -r '.choices[0].message.content' <<<"$response")
  add_message assistant "$reply"

  printf 'llm> %s\n\n' "$reply"
done
```

That's it. Run it:

```
$ bash 02-Chat.sh
Chat with openai/gpt-6-luna. Empty line or Ctrl-D to quit.
you> My name is Anton
llm> Nice to meet you, Anton! How can I help you today?

you> What is my name?
llm> Your name is Anton.
```

Here is what `MESSAGES` looks like right before the second call. This is the entire payload the model sees, nothing more:

```json
[
  { "role": "user",      "content": "My name is Anton" },
  { "role": "assistant", "content": "Nice to meet you, Anton! How can I help you today?" },
  { "role": "user",      "content": "What is my name?" }
]
```

Notice the LLM "remembers" the name only because we sent the whole conversation again on the second call. There is no memory on the server side. The harness *is* the memory. Every turn the array grows and every turn we send all of it.

That's a chatbot in 40 lines of bash. Now let's make it do something.

## Step 3. Giving LLM the tools

A tool is nothing magical. We tell the LLM "here is a function you may ask me to call", and the LLM, instead of answering with text, answers with "please run this function with these arguments". We run it, send the result back, and the LLM continues. See `03-Harness.sh`.

We'll give it one tool, and it's the biggest hammer there is: `bash`.

```bash
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
```

This JSON goes into every request as `tools`, next to `messages`. `call_llm` grows by one field and becomes a single pipeline: jq builds the request and curl reads it from stdin with `-d @-`. The conversation is resent in full on every call and only ever grows, and a command line is capped at 1 MB on macOS, so the body never becomes an argument.

```bash
call_llm() {
  jq -n --arg model "$MODEL" --argjson messages "$1" --argjson tools "$TOOLS" \
    '{model: $model, max_tokens: 8000, messages: $messages, tools: $tools}' |
  curl -sS https://openrouter.ai/api/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -d @-
}
```

We also need to append three different shapes of message now: the user's text, the assistant's reply, and a tool result. Rather than three functions, `add_message` takes jq arguments and an object expression, so every call site spells out the exact JSON it appends:

```bash
add_message() {
  MESSAGES=$(jq --argjson m "$(jq -nc "$@")" '. + [$m]' <<<"$MESSAGES")
}

add_message --arg c "$input" '{role: "user", content: $c}'
add_message --argjson m "$message" '$m'
add_message --arg id "$call_id" --rawfile c <(printf '%s' "$result") \
  '{role: "tool", tool_call_id: $id, content: $c}'
```

The last one uses `--rawfile` with a process substitution for the same reason curl uses `-d @-`: a tool that dumps a big file must not blow the command line.

The only other new piece is running the command and capturing everything the model needs to know about what happened:

```bash
run_tool() {
  local output status=0
  output=$(bash -c "$1" 2>&1) || status=$?
  printf '%s\n[exit code: %d]' "$output" "$status"
}
```

Now the loop. Previously it was: user says something, LLM replies, print. With tools there is a second, inner loop: LLM replies, if the reply has `tool_calls` run them, append results as `tool` messages, call the LLM again. Only when a reply has no tool calls do we print it and hand control back to the user.

```bash
add_message --arg c "$input" '{role: "user", content: $c}'

while true; do
  response=$(call_llm "$MESSAGES")
  message=$(jq -ce '.choices[0].message' <<<"$response") ||
    { printf 'ERROR: %s\n\n' "$(jq -r '.error.message // .' <<<"$response")"; break; }

  add_message --argjson m "$message" '$m'   # echo it back verbatim, tool_calls and all

  if ! jq -e '.tool_calls | length > 0' <<<"$message" >/dev/null; then
    printf 'llm> %s\n\n' "$(jq -r '.content' <<<"$message")"
    break
  fi

  while IFS= read -r call; do
    call_id=$(jq -r '.id' <<<"$call")
    command=$(jq -r '.function.arguments | fromjson | .command' <<<"$call")

    printf 'bash> %s\n' "$command"
    result=$(run_tool "$command")
    add_message --arg id "$call_id" --rawfile c <(printf '%s' "$result") \
      '{role: "tool", tool_call_id: $id, content: $c}'
  done < <(jq -c '.tool_calls[]' <<<"$message")
done
```

Two details worth knowing. The assistant message that contains `tool_calls` has to go back into the history exactly as we received it, so we append the raw JSON rather than rebuilding it. And each tool result carries the `tool_call_id` it answers, so the API can match them up.

The script has two small extras not shown above. While curl waits on the model, a background subshell redraws `thinking Ns` on the same line once a second, and `kill $!` stops it when the response lands. And if the reply was cut off by `max_tokens`, the `arguments` string can be truncated and unparseable; the script catches that and sends the model an error instead of crashing.

That inner loop is the whole "agent". Everything else, Claude Code, Codex, Cursor and friends, is this loop plus a lot of polish.

Let's try it:

```
$ bash 03-Harness.sh
Agent with bash tool (openai/gpt-6-luna). Empty line or Ctrl-D to quit.
you> what's the weather in Toronto?
bash> curl -s 'wttr.in/Toronto?format=3'
      Toronto: ⛅️ +12°C
      [exit code: 0]
llm> It's currently partly cloudy and about 12°C in Toronto.
```

Ask the chatbot from step 2 the same question and it will tell you it has no access to real-time data. Same model, same question. The difference is the `tools` field in the request. The model saw there was a `bash` tool, figured that a shell means it can reach the network, picked `curl` and a weather service on its own, read the output and turned it into an answer. We never mentioned curl, wttr.in or the weather anywhere in the script. That's the whole point of tools: the model does the planning, the harness just runs what it's asked to.

Here is the `MESSAGES` array after that exchange. Five messages, two LLM calls. The first call returned the message with `tool_calls`, the second one returned the final text:

```json
[
  {
    "role": "system",
    "content": "You are a helpful assistant running on the user's machine. Use the bash tool ..."
  },
  {
    "role": "user",
    "content": "what's the weather in Toronto?"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_x7Kq2",
        "type": "function",
        "function": {
          "name": "bash",
          "arguments": "{\"command\": \"curl -s 'wttr.in/Toronto?format=3'\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_x7Kq2",
    "content": "Toronto: ⛅️ +12°C\n[exit code: 0]"
  },
  {
    "role": "assistant",
    "content": "It's currently partly cloudy and about 12°C in Toronto."
  }
]
```

A few things to spot. The `arguments` field is a JSON string inside JSON, which is why the script does `fromjson` on it. The `tool` message answers a specific `tool_call_id`. And the tool output is just text; the model reads `[exit code: 0]` the same way you would. Add `jq . <<<"$MESSAGES" >&2` after any `add_message` call to watch this array grow live.

And the promised finale:

```
you> write a tetris game in python, make sure it runs
bash> python3 --version
      Python 3.13.2
      [exit code: 0]
bash> cat > tetris.py <<'EOF'
      #!/usr/bin/env python3
      """A small, dependency-free Tetris game. Run with: python3 tetris.py"""
      ...
bash> python3 -c "import ast; ast.parse(open('tetris.py').read())"
      [exit code: 0]
bash> python3 -c "import tkinter"
      ModuleNotFoundError: No module named '_tkinter'
      [exit code: 1]
bash> cat > tetris.py <<'EOF'
      ...
llm> Done. tetris.py is written. Tkinter wasn't available on this machine, so the game falls
     back to a curses version that runs in the terminal. Run it with: python3 tetris.py
```

Look at what happened there. The model checked the Python version, wrote the file, verified it parses, discovered Tkinter was missing, and rewrote the game with a terminal fallback. Nobody told it to do any of that. We gave it one tool and a loop; the planning came from the model.

The resulting `tetris.py` is in the repo. It runs.

A word of warning: this script runs whatever the model asks, with your permissions, no questions asked. It's a tutorial. Read the commands as they scroll by, and don't run it in a directory you care about.

## That's all

Three scripts, about 100 lines of bash in total once you take out the comments:

1. `curl` to call the LLM, `jq` to read the answer.
2. A JSON array for history and a loop around the call. That's a chat.
3. A tool definition, a function to run it, and an inner loop that keeps going until the model stops asking for tools. That's an agent.

Everything a real coding agent adds on top, more tools, permissions, context management, nicer input, is engineering around this core. The core fits on one screen.

## What's next

Claude Code and Codex are modern cars: airbags, power windows, AC. What we built here is an engine, a transmission, a chassis and four wheels. As bare as it gets, but it drives. A few things you can add in an afternoon:

- Load `AGENTS.md` from the current directory into the system prompt, so the agent knows the project's conventions.
- Input history: `read -e` already uses readline, so one `history -s "$input"` after each read gives you up/down arrows.
- Ask for approval before running a tool call. The warning above becomes a feature.
- Cap tool output and add a timeout to `run_tool`, so one `cat` of a huge file or a hung command can't wreck the session.
- Save `MESSAGES` to a file after each turn and load it on start. That's session resume.
- More tools: `read_file`, `write_file`, `edit_file`. Each one is a schema and a function.
