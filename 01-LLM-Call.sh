source .env

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