# Qwen3 4B with Ollama

SimplyDoc defaults to Qwen3 4B Instruct (about 2.5 GB download) without an AI API key. OCR and retrieval remain local. Gemini remains optional and is never used as a fallback. GPT-OSS is still available by explicitly changing OLLAMA_MODEL, but consumed too much memory on this laptop.

1. Install [Ollama for Windows](https://ollama.com/download/windows) and start it.
2. In PowerShell, download the model:

       ollama pull qwen3:4b-instruct-2507-q4_K_M

3. Use these settings in the project-root .env:

       AI_PROVIDER=ollama
       OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
       EMBEDDING_PROVIDER=local
       OLLAMA_BASE_URL=http://127.0.0.1:11434

4. Start SimplyDoc with .\start.ps1. The workspace shows whether Ollama is reachable and the model is installed. Click Check again after setup. Installation status does not prove that enough memory is available for inference.
5. Scanned uploads pause at **Check extracted text**. Select the original PDF for a browser-only preview, correct OCR errors, mark unreadable passages as [unclear], then choose **Save text and analyze**. Existing documents have a correction button too. Saving clears obsolete analysis and chat; the original extraction remains available. Key terms include source quotes and page references. Scanned or uncertain values remain marked for verification.

## Historical GPT-OSS measurements and deployment

The Ollama model is approximately 14 GB. Its model page describes operation with as little as 16 GB memory, but actual requirements include context, the operating system, and other apps. The development laptop has approximately 16 GB RAM and a 4 GB RTX 3050; initially only about 2 GB RAM was free. After freeing resources, Ollama 0.33.3 and GPT-OSS 20B were installed successfully. With about 9.7 GB RAM free before loading, a live sample review and cited chat passed on September 10, 2026. The first short request including model load took 145 seconds; a later warm chat took about 13 seconds. These timings are not a guarantee for longer scanned documents. A machine with more available RAM/VRAM is recommended for usable performance; measure with your real documents.

SimplyDoc uses a context sized to each request, up to 32K, low reasoning effort and one concurrent inference request per backend process. Long documents are automatically split into bounded review parts. Every extracted section is assigned to one part, validated results are combined, and completed parts are saved for retry. The overview is a sequence of part summaries; cross-part implications may need additional review. Each part targets at most 1,800 source bytes (larger individual sections remain intact if they fit the context), up to 2 important terms and flags, and 1,000 output tokens. Invalid structured answers or source citations trigger one fresh attempt; a second validation failure produces a specific error. Hindi quotes must remain verbatim, with translations confined to explanations. Inference has a five-minute timeout. Errors identify missing models, unavailable servers and incomplete answers. Reasoning traces are discarded; only final answers are validated and stored.

In Docker Desktop on Windows, the Compose default reaches Ollama on the host through host.docker.internal:11434; the host service must accept the connection. For Linux or another host, set OLLAMA_DOCKER_URL explicitly. Keep the inference server on a trusted private network. Public hosting requires a reachable inference server; a remote Render/Railway app cannot reach Ollama on your laptop through localhost. The free web instance does not run the 20B model itself.

No API token charges apply to your own local inference, but hardware, electricity and rented servers are not free. No automatic cloud routing occurs.

Sources: [GPT-OSS model](https://ollama.com/library/gpt-oss), [Ollama chat API](https://docs.ollama.com/api/chat), [reasoning settings](https://docs.ollama.com/capabilities/thinking).
