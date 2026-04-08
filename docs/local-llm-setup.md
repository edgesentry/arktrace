# Local LLM Setup (macOS)

For macOS users (Intel or Apple Silicon), you can run inference locally without API keys or costs. This is particularly useful for generating analyst briefs and answering analyst chat questions in the dashboard.

## What the LLM does in arktrace

The LLM is called in two places:

| Feature | Prompt shape | Typical output |
| :--- | :--- | :--- |
| **Analyst brief (C2)** | Vessel profile (MMSI, flag, confidence score, top SHAP signals) + 3 recent GDELT geopolitical events | One paragraph citing a specific event and explaining how it connects to the vessel's risk score |
| **Analyst chat (C6)** | Fleet overview (top 10 watchlist candidates) + optional vessel detail + analyst question | Direct factual answer grounded in the provided data |

### Task requirements

The prompts are structured and data-dense but short (typically 500–1 200 tokens in, 150–300 tokens out). The LLM does not need to reason from general knowledge — all facts are supplied in the context. What matters is:

- **Instruction following** — stay within the one-paragraph brief format; cite the event given, do not hallucinate new ones
- **Structured output fidelity** — refer to specific field values (MMSI, flag state, confidence score) by name
- **Low latency** — briefs are streamed live to the analyst; a 3B model at 50–80 tok/s on Apple Silicon feels instant; a 7B model at 20–40 tok/s is still acceptable

A frontier-class model is not needed. The task is closer to *templated summarisation* than *open-ended reasoning*.

---

## Recommended Models

Model IDs and full config blocks live in **`.env.example`** — that is the single source of truth.

The recommended model for shadow fleet analysis is **Qwen 2.5 Coder 7B (Instruct 4-bit)** as it provides the best balance of speed and instruction-following for maritime data.

---

## Option A — llama-cpp-python (zero external server, any hardware)

The simplest setup: no separate server process, no GPU required. Runs on any laptop with 8 GB RAM via CPU inference.

**1. Install the package:**
```bash
uv pip install llama-cpp-python
# Apple Silicon — build with Metal for faster inference:
CMAKE_ARGS="-DGGML_METAL=on" uv pip install llama-cpp-python --force-reinstall
```

**2. Download a GGUF model** (Gemma 4B Instruct Q4_K_M recommended, ~2.5 GB):
```bash
# Using huggingface-hub CLI:
pip install huggingface-hub
huggingface-cli download bartowski/gemma-3-4b-it-GGUF \
    gemma-3-4b-it-Q4_K_M.gguf --local-dir ~/models/
```

**3. Configure `.env`:**
```bash
LLM_PROVIDER=llamacpp
LLAMACPP_MODEL_PATH=/Users/yourname/models/gemma-3-4b-it-Q4_K_M.gguf
```

**4. Start the dashboard** — no other process needed:
```bash
uv run uvicorn src.api.main:app --reload
```

The model is loaded once on first request and reused for subsequent briefs. If `LLAMACPP_MODEL_PATH` is unset or the file is missing, the dashboard loads normally and brief generation returns a "LLM not configured" placeholder.

**Memory guide:**

| Model | Quantisation | File size | RAM needed |
|---|---|---|---|
| Gemma 4B Instruct | Q4_K_M | ~2.5 GB | 8 GB |
| Gemma 4B Instruct | Q8_0 | ~4.3 GB | 8 GB |
| Gemma 12B Instruct | Q4_K_M | ~7.5 GB | 16 GB |

---

## Option B — mlx-lm proxy (Apple Silicon, shared with Claude Code)

We use the **`mlx-lm-coding-agent-proxy`** to run a local LLM that is compatible with both OpenAI and Anthropic API standards. This allows `arktrace` and `Claude Code` to share the same model instance in memory.

1. **Install and Start the Proxy**:
   Follow the instructions in the [mlx-lm-coding-agent-proxy](https://github.com/yohei1126/mlx-lm-coding-agent-proxy) repository to install and start the proxy server.

2. **Configure `.env`**:
   Uncomment the "Unified Local Proxy" block in your `.env` file:
   ```bash
   LLM_PROVIDER=mlx
   LLM_BASE_URL=http://localhost:8888/v1
   LLM_API_KEY=local
   LLM_MODEL=mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
   ```

3. **Verify Connection**:
   Once the proxy is running on port 8888, the `arktrace` dashboard will automatically use it for generating briefs and chat responses.

---

## Hardware & Performance Notes

### Memory Requirements
- **4B models (Gemma 4B Q4_K_M via llama-cpp-python):** ~2.5 GB model + ~1 GB overhead. Works on 8 GB machines.
- **7B models (Qwen 2.5 7B):** ~8 GB RAM. Recommended for 16 GB+ machines.

### Processor Support
- **Apple Silicon (M1/M2/M3/M4):** Option A (llama-cpp-python with Metal) or Option B (MLX proxy). Metal build of llama-cpp-python gives near-MLX performance.
- **Intel Mac / Linux CPU:** Option A only (llama-cpp-python CPU inference). Option B (MLX) is Apple Silicon only.
