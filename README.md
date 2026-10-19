# bash-harness

A tutorial on building an agentic harness in nothing but bash, `curl` and `jq`.
Each numbered script adds one idea on top of the previous one. The full
walkthrough is in [ARTICLE.md](ARTICLE.md).

## What you need

- A terminal with `bash`, `curl` and `jq`
- An [OpenRouter](https://openrouter.ai) API key, or any other OpenAI-compatible endpoint with tool calling

Setup: put `OPENROUTER_API_KEY=sk-or-...` in `.env`.

## Steps

| Step | File | Adds |
|------|------|------|
| 01 | `01-LLM-Call.sh` | One raw `curl` call to a chat completions endpoint. |
| 02 | `02-Chat.sh` | `call_llm` as a function, the conversation as a JSON array, and a read/call/print loop. |
| 03 | `03-Harness.sh` | A `bash` tool: the model asks to run commands, the harness runs them and feeds results back until the model answers. |

Run any step with `bash 0N-....sh`.

`tetris.py` is what step 03 produced when asked to "write a tetris game in python, make sure it runs". Try it with `python3 tetris.py`.

## Warning

`03-Harness.sh` runs whatever the model asks for, with your permissions and
no confirmation. It is a tutorial. Read the commands as they scroll by and
don't run it in a directory you care about.

## License

MIT, see [LICENSE](LICENSE).
