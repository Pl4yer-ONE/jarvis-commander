import ollama
tools = [{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather",
    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
  }
}]
stream = ollama.chat(model='qwen2.5:3b', messages=[{"role": "user", "content": "What's the weather in Tokyo?"}], tools=tools, stream=True)
for chunk in stream:
    print(chunk)
