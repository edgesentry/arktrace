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

| RAM Tier | Model | MLX ID (Hugging Face) | Ollama ID | Why it fits |
| :--- | :--- | :--- | :--- | :--- |
| **≤ 4 GB — Recommended** | Llama 3.2 3B | `mlx-community/Llama-3.2-3B-Instruct-4bit` | `llama3.2:3b` | Strong instruction following at 3B; runs at ~80 tok/s on M-series; well-tested with the brief and chat prompts |
| **≤ 4 GB — Alternative** | Qwen 2.5 3B | `mlx-community/Qwen2.5-3B-Instruct-4bit` | `qwen2.5:3b` | Slightly better structured-output fidelity than Llama at the same size; good fallback if Llama output feels loose |
| **≤ 8 GB — Higher quality** | Qwen 2.5 7B | `mlx-community/Qwen2.5-7B-Instruct-4bit` | `qwen2.5:7b` | Noticeably better at multi-hop reasoning (e.g. connecting an ownership chain to a sanctions regime in chat); use on 16 GB+ machines |

---

## ⚠️ Docker Access Note
If you are running the **MPOL Dashboard or Pipeline inside Docker**, you cannot use `localhost` in your `.env` file to reach the LLM server. You must use **`host.docker.internal`** to allow the container to communicate with your Mac host:

*   **MLX:** `LLM_BASE_URL=http://host.docker.internal:8080/v1`
*   **Ollama:** `LLM_BASE_URL=http://host.docker.internal:11434/v1`

---

## Option A: MLX LM (Recommended for Apple Silicon)

Optimized for Apple Silicon. MLX LM runs quantized models natively on the Apple Neural Engine. It is the fastest local option on M-series Macs.

1. **Install the dependencies** (requires Python 3.10+):
   ```bash
   # Sync the environment and include the mlx extra
   uv sync --extra mlx
   ```

2. **Start the OpenAI-compatible server**:
   Replace `--model` with your chosen model ID from the table above.
   ```bash
   # Example: Running Llama 3.2 3B
   uv run mlx_lm.server \
     --model mlx-community/Llama-3.2-3B-Instruct-4bit \
     --port 8080
   ```

3. **Update `.env`**:
   ```env
   LLM_PROVIDER=mlx
   LLM_BASE_URL=http://localhost:8080/v1  # Use host.docker.internal if running in Docker
   LLM_API_KEY=local
   LLM_MODEL=mlx-community/Llama-3.2-3B-Instruct-4bit
   ```

---

## Option B: Ollama (Intel & Apple Silicon)

Supports Metal acceleration on Apple Silicon and CPU on Intel.

1. **Install via Homebrew**:
   ```bash
   brew install ollama
   ```

2. **Pull a model and start the server**:
   ```bash
   ollama pull llama3.2:3b
   ollama serve
   ```

3. **Update `.env`**:
   ```env
   LLM_PROVIDER=ollama
   LLM_BASE_URL=http://localhost:11434/v1 # Use host.docker.internal if running in Docker
   LLM_API_KEY=local
   LLM_MODEL=llama3.2:3b
   ```

---

## Hardware & Performance Notes

### Memory Requirements
- **3B models (Llama 3.2 3B, Qwen 2.5 3B):** ~4 GB RAM. Runs comfortably on an 8 GB MacBook Air.
- **7B models (Qwen 2.5 7B):** ~8 GB RAM. Recommended for 16 GB+ machines.

### Processor Support
- **MLX LM:** Native support for **Apple Silicon (M1/M2/M3/M4)** only.
- **Ollama:** Supports both **Apple Silicon** (Metal) and **Intel** (CPU inference).
