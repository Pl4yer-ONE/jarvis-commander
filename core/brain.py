"""
Max — Brain Module (LLM Integration)

Routes prompts to the configured LLM backend and handles tool calling.
Primary: Ollama (local, no API key needed)
Fallback: OpenAI or Google Gemini (requires API keys in .env)

All LLM calls support streaming for real-time token output.
"""

import json
import logging
import re
from typing import Any, Generator

from core.memory import get_user_context, log_command, log_chat

logger = logging.getLogger("max.brain")


class Brain:
    """LLM integration with tool-calling support and conversation memory."""

    def __init__(self, config, skill_registry=None):
        self.config = config
        self.skill_registry = skill_registry
        self.conversation_history: list[dict[str, str]] = []
        self._client = None
        self._backend = str(config.llm_backend.value) if hasattr(config.llm_backend, 'value') else str(config.llm_backend)
        self._ollama_no_tools = False

    # ── Initialization ───────────────────────────────────────

    def initialize(self):
        """Initialize the LLM client based on the configured backend."""
        init_map = {
            "ollama": self._init_ollama,
            "openai": self._init_openai,
            "gemini": self._init_gemini,
        }
        init_fn = init_map.get(self._backend)
        if not init_fn:
            raise ValueError(f"Unknown LLM backend: {self._backend}")
        init_fn()

    def _init_ollama(self):
        """Initialize Ollama client."""
        try:
            import ollama
            self._client = ollama.Client(host=self.config.ollama_host)
            self._client.list()
            logger.info("Ollama connected — %s @ %s", self.config.ollama_model, self.config.ollama_host)
        except ImportError:
            raise RuntimeError("ollama package not installed. Run: pip install ollama")
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.config.ollama_host}. "
                f"Is Ollama running? Start: ollama serve\nError: {e}"
            )

    def _init_openai(self):
        """Initialize OpenAI client."""
        if not self.config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set in .env")
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.config.openai_api_key)
            logger.info("OpenAI ready — model: %s", self.config.openai_model)
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

    def _init_gemini(self):
        """Initialize Google Gemini client."""
        if not self.config.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set in .env")
        try:
            from google import genai
            self._client = genai.Client(api_key=self.config.gemini_api_key)
            logger.info("Gemini ready — model: %s", self.config.gemini_model)
        except ImportError:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

    # ── Tool Definitions ─────────────────────────────────────

    def _get_tool_definitions(self) -> list[dict]:
        """Generate tool definitions from the skill registry."""
        if not self.skill_registry:
            return []
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for name, info in self.skill_registry.list_skills().items()
        ]

    # ── Startup Routine ──────────────────────────────────────

    def perform_startup_routine(self, speaker):
        """Autonomous startup: fetch news and announce."""
        log_chat("SYS", "Startup routine initiated.")
        try:
            from skills.online_ops import search_web
            results = search_web("latest tech news today")

            prompt = (
                "You are Max. You just booted up and scraped this news. "
                "Briefly summarize in 1-2 intense sentences to announce you're online.\n\n"
                f"{results}"
            )
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": prompt},
            ]
            response = self._chat(messages, tools=[])
            summary = response["content"]
            log_chat("MAX", summary)
            if speaker:
                speaker.speak(summary)
            self.conversation_history.append({"role": "assistant", "content": summary})
            log_chat("SYS", "Startup complete.")
        except Exception as e:
            logger.error("Startup error: %s", e)
            log_chat("ERROR", str(e))

    # ── Backend Chat Methods ─────────────────────────────────

    def _chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """Dispatch to the active backend."""
        dispatch = {
            "ollama": self._chat_ollama,
            "openai": self._chat_openai,
            "gemini": self._chat_gemini,
        }
        return dispatch[self._backend](messages, tools)

    def _chat_ollama(self, messages: list[dict], tools: list[dict]) -> dict:
        """Send chat to Ollama and return response."""
        kwargs: dict[str, Any] = {
            "model": self.config.ollama_model,
            "messages": list(messages),
        }

        use_native_tools = tools and not self._ollama_no_tools
        if use_native_tools:
            kwargs["tools"] = tools
        elif tools:
            kwargs["messages"] = self._inject_tools_into_prompt(messages, tools)

        try:
            response = self._client.chat(**kwargs)
        except Exception as e:
            if "does not support tools" in str(e) and tools:
                logger.warning("Model lacks tool support — using prompt-based fallback.")
                self._ollama_no_tools = True
                kwargs.pop("tools", None)
                kwargs["messages"] = self._inject_tools_into_prompt(messages, tools)
                response = self._client.chat(**kwargs)
            else:
                raise

        msg = response.get("message", response) if isinstance(response, dict) else response.message
        content = msg.get("content", "") if isinstance(msg, dict) else (msg.content or "")
        raw_tools = msg.get("tool_calls", []) if isinstance(msg, dict) else (msg.tool_calls or [])

        result = {"content": content, "tool_calls": []}

        if raw_tools:
            for tc in raw_tools:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    result["tool_calls"].append({"name": func.get("name", ""), "arguments": func.get("arguments", {})})
                else:
                    result["tool_calls"].append({"name": tc.function.name, "arguments": tc.function.arguments})
        elif tools and self._ollama_no_tools:
            parsed = self._parse_tool_calls_from_text(content)
            if parsed:
                result["tool_calls"] = parsed
                result["content"] = self._strip_tool_json(content)

        return result

    def _chat_openai(self, messages: list[dict], tools: list[dict]) -> dict:
        """Send chat to OpenAI."""
        kwargs: dict[str, Any] = {"model": self.config.openai_model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        result = {"content": msg.content or "", "tool_calls": []}
        if msg.tool_calls:
            for tc in msg.tool_calls:
                result["tool_calls"].append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })
        return result

    def _chat_gemini(self, messages: list[dict], tools: list[dict]) -> dict:
        """Send chat to Google Gemini."""
        from google.genai import types

        contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
                continue
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(
                role=role, parts=[types.Part.from_text(text=msg["content"])],
            ))

        gemini_tools = None
        if tools:
            decls = [
                types.FunctionDeclaration(
                    name=t["function"]["name"],
                    description=t["function"]["description"],
                    parameters=t["function"].get("parameters"),
                )
                for t in tools
            ]
            gemini_tools = [types.Tool(function_declarations=decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction, tools=gemini_tools,
        )
        response = self._client.models.generate_content(
            model=self.config.gemini_model, contents=contents, config=config,
        )

        result = {"content": "", "tool_calls": []}
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    result["content"] += part.text
                if part.function_call:
                    fc = part.function_call
                    result["tool_calls"].append({
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    })
        return result

    # ── Tool Injection (for models without native tools) ─────

    def _inject_tools_into_prompt(self, messages: list[dict], tools: list[dict]) -> list[dict]:
        """Embed tool descriptions into the system prompt."""
        tool_lines = []
        for tool in tools:
            func = tool["function"]
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            param_parts = [
                f'{n}: {p.get("type", "any")}{"(required)" if n in required else ""}'
                for n, p in params.items()
            ]
            tool_lines.append(f"  - {func['name']}({', '.join(param_parts)}): {func['description']}")

        block = (
            "\n\nYou have access to tools. To use one, respond with ONLY:\n"
            '```json\n{"tool": "tool_name", "arguments": {"arg1": "value1"}}\n```\n'
            "If you don't need a tool, respond normally.\nAvailable tools:\n" +
            "\n".join(tool_lines)
        )

        return [
            {**msg, "content": msg["content"] + block} if msg["role"] == "system" else msg
            for msg in messages
        ]

    def _parse_tool_calls_from_text(self, text: str) -> list[dict]:
        """Parse JSON tool calls from text response."""
        calls = []
        blocks = re.findall(r'```json\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'(\{[^{}]*"tool"[^{}]*\})', text, re.DOTALL)
        for block in blocks:
            try:
                data = json.loads(block.strip())
                if "tool" in data:
                    calls.append({
                        "name": data["tool"],
                        "arguments": data.get("arguments", data.get("args", {})),
                    })
            except json.JSONDecodeError:
                continue
        return calls

    @staticmethod
    def _strip_tool_json(text: str) -> str:
        """Remove JSON tool call blocks from visible text."""
        return re.sub(
            r'```json\s*\n?\{[^}]*"tool"[^}]*\}\n?\s*```', '', text, flags=re.DOTALL
        ).strip()

    # ── Tool Execution ───────────────────────────────────────

    def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Execute tool calls via the skill registry."""
        results = []
        for call in tool_calls:
            name, args = call["name"], call.get("arguments", {})
            logger.info("🔧 Executing: %s(%s)", name, args)

            if not self.skill_registry:
                results.append({"tool": name, "result": "No skill registry.", "success": False})
                continue

            try:
                output = self.skill_registry.execute(name, args)
                results.append({"tool": name, "result": str(output), "success": True})
                logger.info("✅ %s → %s", name, str(output)[:100])
            except Exception as e:
                error_msg = f"Error: {name}: {e}"
                results.append({"tool": name, "result": error_msg, "success": False})
                logger.error("❌ %s", error_msg)

        return results

    # ── Build Messages ───────────────────────────────────────

    def _build_messages(self, user_input: str | None = None) -> list[dict]:
        """Build the full message list with system prompt + context."""
        system_content = self.config.system_prompt

        # User memory context
        user_ctx = get_user_context()
        if user_ctx:
            system_content += f"\n\nUser context:\n{user_ctx}"

        # Live sensor data from event bus
        try:
            from core.event_bus import get_bus
            bus = get_bus()
            parts = []
            cam = bus.get_state("sentinel.camera")
            if cam and cam.get("status") == "active":
                parts.append(f"📷 Camera: LIVE (last: {cam.get('last_capture', 'N/A')})")

            yolo = bus.get_state("sentinel.yolo")
            if yolo and yolo.get("detections"):
                det_summary = ", ".join(
                    f"{d['object']}@({d['center'][0]},{d['center'][1]})"
                    for d in yolo["detections"][:10]
                )
                parts.append(f"🔍 YOLO: {len(yolo['detections'])} objects: {det_summary}")

            sys_data = bus.get_state("sentinel.system")
            if sys_data and sys_data.get("data"):
                d = sys_data["data"]
                parts.append(
                    f"⚙️ System: CPU {d.get('cpu', '?')}%, RAM {d.get('ram', '?')}%, "
                    f"Disk {d.get('disk_free', '?')} free, Temp {d.get('temp', '?')}"
                )

            usb = bus.get_state("sentinel.usb")
            if usb and usb.get("new_device"):
                parts.append(f"🔌 NEW USB: {usb['new_device']}")

            if parts:
                system_content += "\n\n--- LIVE SENSOR DATA ---\n" + "\n".join(parts)
        except Exception:
            pass

        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.conversation_history[-self.config.max_history * 2:])
        return messages

    # ── Public API ───────────────────────────────────────────

    def think(self, user_input: str) -> str:
        """Process user input through LLM with tool execution. Returns final text."""
        self.conversation_history.append({"role": "user", "content": user_input})
        log_chat("USER", user_input)

        messages = self._build_messages()
        tools = self._get_tool_definitions()

        try:
            response = self._chat(messages, tools)

            iteration = 0
            while response["tool_calls"] and iteration < self.config.max_concurrent_tools:
                iteration += 1
                tool_results = self._execute_tool_calls(response["tool_calls"])
                tool_summary = "\n".join(
                    f"[Tool: {r['tool']}] {'✅' if r['success'] else '❌'} {r['result']}"
                    for r in tool_results
                )
                messages.append({"role": "assistant", "content": response["content"] or "(calling tools)"})
                messages.append({"role": "user", "content": f"Tool results:\n{tool_summary}"})
                response = self._chat(messages, tools)

            final = response["content"] or "Action completed."

            self.conversation_history.append({"role": "assistant", "content": final})
            log_command(user_input, final)
            log_chat("MAX", final)
            self._trim_history()
            return final

        except Exception as e:
            error = f"Error while thinking: {e}"
            logger.error(error)
            return error

    def think_stream(self, user_input: str) -> Generator[str, None, None]:
        """Process input and yield text chunks as they arrive."""
        self.conversation_history.append({"role": "user", "content": user_input})
        log_chat("USER", user_input)

        messages = self._build_messages()
        tools = self._get_tool_definitions()

        try:
            # Resolve tools first (non-streaming)
            response = self._chat(messages, tools)

            iteration = 0
            while response["tool_calls"] and iteration < self.config.max_concurrent_tools:
                iteration += 1
                tool_results = self._execute_tool_calls(response["tool_calls"])
                tool_summary = "\n".join(
                    f"[Tool: {r['tool']}] {'✅' if r['success'] else '❌'} {r['result']}"
                    for r in tool_results
                )
                messages.append({"role": "assistant", "content": response["content"] or "(calling tools)"})
                messages.append({"role": "user", "content": f"Tool results:\n{tool_summary}"})
                response = self._chat(messages, tools)

            if iteration > 0:
                # Tools were used — yield pre-computed answer
                final = response["content"] or "Action completed."
                yield final
            else:
                # No tools — stream token by token
                final = ""
                for chunk in self._stream_dispatch(messages):
                    final += chunk
                    yield chunk

            self.conversation_history.append({"role": "assistant", "content": final})
            log_command(user_input, final)
            log_chat("MAX", final)
            self._trim_history()

        except Exception as e:
            error = f"Error: {e}"
            logger.error(error)
            yield error

    # ── Streaming Dispatch ───────────────────────────────────

    def _stream_dispatch(self, messages: list[dict]) -> Generator[str, None, None]:
        dispatch = {
            "ollama": self._stream_ollama,
            "openai": self._stream_openai,
            "gemini": self._stream_gemini,
        }
        yield from dispatch.get(self._backend, lambda m: iter(["Streaming not supported."]))(messages)

    def _stream_ollama(self, messages: list[dict]) -> Generator[str, None, None]:
        try:
            stream = self._client.chat(
                model=self.config.ollama_model, messages=list(messages), stream=True,
            )
            for chunk in stream:
                msg = chunk.get("message", chunk) if isinstance(chunk, dict) else chunk.message
                content = msg.get("content", "") if isinstance(msg, dict) else (msg.content or "")
                if content:
                    yield content
        except Exception as e:
            logger.error("Ollama stream error: %s", e)

    def _stream_openai(self, messages: list[dict]) -> Generator[str, None, None]:
        try:
            stream = self._client.chat.completions.create(
                model=self.config.openai_model, messages=messages, stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error("OpenAI stream error: %s", e)

    def _stream_gemini(self, messages: list[dict]) -> Generator[str, None, None]:
        from google.genai import types
        contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
                continue
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(
                role=role, parts=[types.Part.from_text(text=msg["content"])],
            ))
        config = types.GenerateContentConfig(system_instruction=system_instruction)
        try:
            stream = self._client.models.generate_content_stream(
                model=self.config.gemini_model, contents=contents, config=config,
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("Gemini stream error: %s", e)

    # ── Utility ──────────────────────────────────────────────

    def _trim_history(self):
        """Trim conversation history to configured max."""
        max_entries = self.config.max_history * 2
        if len(self.conversation_history) > max_entries:
            self.conversation_history = self.conversation_history[-max_entries:]

    def reset_memory(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.info("Memory cleared.")

    # ── Autonomous Methods ───────────────────────────────────

    def autonomous_think(self, context_str: str) -> str:
        """Generate an autonomous thought from context."""
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": context_str},
        ]
        try:
            return self._chat(messages, tools=[]).get("content", "").strip()
        except Exception as e:
            logger.error("Autonomous think error: %s", e)
            return ""

    def vision_analyze(self, image_path: str = None) -> str:
        """Analyze a camera frame using a multimodal vision model."""
        if not image_path:
            image_path = str(self.config.project_root / "data" / "captures" / "cam_latest.jpg")

        try:
            import ollama
            with open(image_path, "rb") as f:
                img_data = f.read()

            response = ollama.chat(
                model=self.config.vision_model,
                messages=[{
                    "role": "user",
                    "content": "Describe what you see in 2-3 sentences. Be specific about people, objects, lighting.",
                    "images": [img_data],
                }],
            )
            msg = response.get("message", response) if isinstance(response, dict) else response.message
            description = msg.get("content", "") if isinstance(msg, dict) else (msg.content or "")
            if description:
                try:
                    from core.event_bus import get_bus
                    from datetime import datetime
                    import asyncio
                    bus = get_bus()
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(bus.publish("sentinel.vision", {
                            "status": "active",
                            "description": description[:300],
                            "timestamp": datetime.now().isoformat(),
                        }))
                    except RuntimeError:
                        pass
                except Exception:
                    pass
                return description
        except FileNotFoundError:
            return "No camera image available."
        except Exception as e:
            logger.debug("Vision model unavailable: %s", e)

        # Fallback to YOLO data
        try:
            from core.event_bus import get_bus
            yolo = get_bus().get_state("sentinel.yolo")
            if yolo and yolo.get("detections"):
                objs = ", ".join(d["object"] for d in yolo["detections"][:8])
                return f"Vision model unavailable. YOLO detects: {objs}"
        except Exception:
            pass
        return "Vision analysis unavailable."

    def free_speak(self, topic: str = None) -> str:
        """Generate spontaneous commentary for autonomous speech."""
        if topic:
            prompt = f"Say something brief and interesting about: {topic}. 1-2 sentences. Be opinionated."
        else:
            prompt = ("Make a brief spontaneous comment, observation, or question. "
                      "1-2 sentences. Be interesting.")

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            return self._chat(messages, tools=[]).get("content", "").strip()
        except Exception as e:
            logger.error("Free speak error: %s", e)
            return ""
