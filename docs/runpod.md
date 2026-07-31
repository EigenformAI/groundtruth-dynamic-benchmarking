# Running the models on RunPod (vLLM)

Notes for preparing the vLLM server on RunPod before running `main.py` in generate mode. `start_eval.sh` automates most of this; these are the raw start commands for doing it manually with the vLLM container image.

## Model registry (`configs/models.json`)

The model menu in `start_eval.sh` is built from `configs/models.json` — a JSON array (no comments allowed), one entry per model variant:

```json
[
  {
    "label": "Base",
    "model": "QuantTrio/gemma-4-31B-it-AWQ"
  },
  {
    "label": "My fine-tune",
    "model": "QuantTrio/gemma-4-31B-it-AWQ",
    "lora": "your-org/your-lora-adapter",
    "tokenizer": "your-org/your-lora-adapter",
    "max_lora_rank": 64
  }
]
```

| Field | Required | Meaning |
|---|---|---|
| `label` | yes | Display name — shown in the menu and used as the model label in exports |
| `model` | yes | Base model repo on Hugging Face |
| `lora` | no | LoRA adapter repo; omit for a plain base model |
| `tokenizer` | no | Tokenizer repo; defaults to the `lora` value |
| `max_lora_rank` | no | LoRA rank cap passed to vLLM; defaults to 64 |

Shared vLLM flags (context length, GPU utilization, generation config, ...)
live in `VLLM_COMMON_ARGS` in `start_eval.sh`.

## GPU sizing

- Most tests here were run on an **RTX 6000 ADA**.
- For r128 LoRA at `--max-model-len 192000`, an **H100 SXM** may be needed; r32 fits on the RTX 6000 ADA.

## vLLM start commands

The HF model and tokenizer can be swapped as needed. Adapters must be uploaded to Hugging Face first — that avoids manual vLLM preparation on the pod, and afterwards `main.py --mode api` can be used to get the answers.

`benchmark` in the commands below is the alias vLLM serves the model under.
`main.py` asks for it by that name, so keep it as-is whichever model you load —
it is what decouples `main.py` from the model choice. It must match
`ADAPTER_NAME` in `start_eval.sh`.

### Base model (vanilla Gemma)

```
--model QuantTrio/gemma-4-31B-it-AWQ --served-model-name benchmark --tensor-parallel-size 1 --gpu-memory-utilization 0.90 --max-model-len 192000 --override-generation-config '{"repetition_penalty": 1.1, "frequency_penalty": 0.3, "temperature": 0, "top_p": 1}' --enable-auto-tool-choice --tool-call-parser gemma4
```

### With a LoRA adapter

Swap `your-org/your-lora-adapter` for your own adapter repo, and set
`--max-lora-rank` to the rank it was trained at.

```
--model QuantTrio/gemma-4-31B-it-AWQ --enable-lora --lora-modules benchmark=your-org/your-lora-adapter --tokenizer your-org/your-lora-adapter --tensor-parallel-size 1 --gpu-memory-utilization 0.90 --max-model-len 192000 --max-lora-rank 64 --override-generation-config '{"repetition_penalty": 1.1, "frequency_penalty": 0.3, "temperature": 0, "top_p": 1}' --enable-auto-tool-choice --tool-call-parser gemma4
```

## opencode mode

opencode must be installed and the project set up manually before running `main.py --mode opencode` locally. Occasionally opencode fails to start from the CLI; starting it once from the TUI usually clears this.
