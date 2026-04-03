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

Model IDs and full config blocks live in **`.env.example`** — that is the single source of truth. The table below explains which option to pick and why.

| RAM Tier | Model | Why it fits |
| :--- | :--- | :--- |
| **≤ 4 GB — Recommended** | Llama 3.2 3B | Strong instruction following at 3B; runs at ~80 tok/s on M-series; well-tested with the brief and chat prompts |
| **≤ 4 GB — Alternative** | Qwen 2.5 3B | Slightly better structured-output fidelity than Llama at the same size; good fallback if Llama output feels loose |
| **≤ 8 GB — Higher quality** | Qwen 2.5 7B | Noticeably better at multi-hop reasoning (e.g. connecting an ownership chain to a sanctions regime in chat); use on 16 GB+ machines |

---

## Setup

1. **Install prerequisites** for your chosen backend:

   - **MLX LM** (Apple Silicon only):
     ```bash
     uv sync --extra mlx
     ```
   - **Ollama** (Intel + Apple Silicon):
     ```bash
     brew install ollama
     ```

2. **Configure `.env`** — copy the matching block from `.env.example` and uncomment it. Each block is labeled with the backend, model, and RAM tier.

3. **Start the server** — the script reads `LLM_PROVIDER` and `LLM_MODEL` directly from `.env`:
   ```bash
   ./scripts/start_llm_server.sh
   ```
   For MLX this starts an OpenAI-compatible server on port 8080. For Ollama it pulls the model (if not already cached) then starts the server on port 11434.

---

## Hardware & Performance Notes

### Memory Requirements
- **3B models (Llama 3.2 3B, Qwen 2.5 3B):** ~4 GB RAM. Runs comfortably on an 8 GB MacBook Air.
- **7B models (Qwen 2.5 7B):** ~8 GB RAM. Recommended for 16 GB+ machines.

### Processor Support
- **MLX LM:** Native support for **Apple Silicon (M1/M2/M3/M4)** only.
- **Ollama:** Supports both **Apple Silicon** (Metal) and **Intel** (CPU inference).
