#!/usr/bin/env bash
set -euo pipefail

unset VIRTUAL_ENV

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNPOD_GRAPHQL="https://api.runpod.io/graphql"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
OPENCODE_AUTH="$HOME/.local/share/opencode/auth.json"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

# API keys are validated lazily, once the chosen path is known:
# scoring only needs OPENROUTER_API_KEY, generation needs RUNPOD_API_KEY + HF_TOKEN — so a scoring-only run works without any RunPod setup.
require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Error: $name is not set. Add it to .env or export it (needed for $2)." >&2
    exit 1
  fi
}

# vLLM start command settings. The model/LoRA variants live in configs/models.json; 
# everything below is shared by all of them.
OGC='{\"repetition_penalty\":1.1,\"frequency_penalty\":0.3,\"temperature\":0,\"top_p\":1,\"top_k\":-1}'
VLLM_COMMON_ARGS="--tensor-parallel-size 1 --gpu-memory-utilization 0.90 --max-model-len 192000 --max-num-seqs 4 --override-generation-config $OGC --enable-auto-tool-choice --tool-call-parser gemma4"
ADAPTER_NAME="benchmark"  # served-model/LoRA-adapter alias main.py asks for
MODELS_CONFIG="$SCRIPT_DIR/configs/models.json"
RUBRICS_CONFIG="$SCRIPT_DIR/configs/rubrics.json"

# Builds DOCKER_ARGS + MODEL_LABEL from the models.json entry at index $1.
build_docker_args() {
  local idx="$1" model lora tokenizer rank
  MODEL_LABEL=$(jq -r ".[$idx].label" "$MODELS_CONFIG")
  MODEL_PROVIDER=$(jq -r ".[$idx].provider // \"vllm\"" "$MODELS_CONFIG")
  model=$(jq -r ".[$idx].model" "$MODELS_CONFIG")

  if [[ "$MODEL_PROVIDER" == "openrouter" ]]; then
    MODEL_FLAG="--model openrouter/$model"
    DOCKER_ARGS=""
    return
  fi

  lora=$(jq -r ".[$idx].lora // empty" "$MODELS_CONFIG")
  tokenizer=$(jq -r ".[$idx].tokenizer // empty" "$MODELS_CONFIG")
  rank=$(jq -r ".[$idx].max_lora_rank // empty" "$MODELS_CONFIG")

  if [[ -n "$lora" ]]; then
    DOCKER_ARGS="$model --enable-lora --lora-modules $ADAPTER_NAME=$lora --tokenizer ${tokenizer:-$lora} --max-lora-rank ${rank:-64} $VLLM_COMMON_ARGS"
  else
    DOCKER_ARGS="$model --served-model-name $ADAPTER_NAME $VLLM_COMMON_ARGS"
  fi
}

echo ""
echo "=== Task ==="
echo "  1) Generate answers — ask the model each rubric question (creates a RunPod GPU pod)"
echo "  2) Score answers    — judge already-generated answer files (OpenRouter only, no GPU)"
read -rp "Choice [1-2, default: 1]: " TASK_CHOICE
case "${TASK_CHOICE:-1}" in
  1) DO_SCORE=false ;;
  2) DO_SCORE=true ;;
  *) echo "Invalid choice"; exit 1 ;;
esac

# The rubric file is the question set when generating and the grading key when scoring (it also carries the opencode project-dir), so it is asked for both tasks. The menu is built from the same registry main.py resolves --rubric against, so the two can never drift apart.
echo ""
echo "=== Rubric / grading key ==="
N_RUBRICS=$(jq 'length' "$RUBRICS_CONFIG")
jq -r 'to_entries[] | "  \(.key + 1)) \(.value.label)"' "$RUBRICS_CONFIG"
read -rp "Choice [1-$N_RUBRICS, default: 1]: " RUBRIC_CHOICE
RUBRIC_CHOICE="${RUBRIC_CHOICE:-1}"
if ! [[ "$RUBRIC_CHOICE" =~ ^[0-9]+$ ]] || (( RUBRIC_CHOICE < 1 || RUBRIC_CHOICE > N_RUBRICS )); then
  echo "Invalid choice"; exit 1
fi
RUBRIC_FLAG="--rubric $(jq -r ".[$((RUBRIC_CHOICE - 1))].key" "$RUBRICS_CONFIG")"

if ! uv run python main.py $RUBRIC_FLAG --check-rubric; then
  echo "Aborted — fix the rubric and re-run." >&2
  exit 1
fi

SCORE_FLAG=""
NOFLEX_FLAG=""
API_FLAG=""
SCORE_FLAGS_ARR=()
SCORE_MULTI_RUN=false
MODEL_A_LABELS=()
MODEL_B_LABELS=()
OUTPUT_FILES_ARR=()
NEED_RUNPOD=true
MODE="opencode"
EXPLORE_FLAG=""
WORKERS=1
DOCKER_ARGS=""
MODEL_FLAG=""
MODEL_PROVIDER="vllm"
MODEL_LABEL=""
MODEL_A_LABEL=""
MODEL_B_LABEL=""

if [[ "$DO_SCORE" == "true" ]]; then
  require_env OPENROUTER_API_KEY "the LLM judge"

  # Prompt until we get a path to a file that actually exists — an empty or wrong path here would otherwise surface much later as a confusing argparse/FileNotFoundError inside main.py.
  _read_answer_file() {
    local prompt="$1" path
    while true; do
      if ! read -rp "$prompt" path; then
        echo "    Aborted (end of input)." >&2
        exit 1
      fi
      if [[ -z "$path" ]]; then
        echo "    A file path is required." >&2
      elif [[ ! -f "$path" ]]; then
        echo "    File not found: $path" >&2
      else
        echo "$path"
        return
      fi
    done
  }

  # Convert .jsonl to .json if needed
  _convert_if_jsonl() {
    local path="$1"
    if [[ "$path" == *.jsonl ]]; then
      local out="${path%.jsonl}.json"
      echo "  Converting JSONL → JSON: $path" >&2
      uv run python "$SCRIPT_DIR/scripts/convert_jsonl.py" "$path" "$out" >&2
      echo "$out"
    else
      echo "$path"
    fi
  }

  # Global scoring config (asked once, upfront)
  echo ""
  read -rp "  Export the results to Google Sheets when done? [y/N]: " EXPORT_CHOICE
  EXPORT_ON=false
  if [[ "$(echo "$EXPORT_CHOICE" | tr '[:upper:]' '[:lower:]')" == "y" ]]; then
    EXPORT_ON=true
    require_env GOOGLE_SERVICE_ACCOUNT_FILE "the Google Sheets export"
    require_env GOOGLE_SHEET_ID "the Google Sheets export"
  fi

  echo ""
  echo "  Judge service tier:"
  echo "    1) flex (cheaper ~½ cost, slower / may hit 429)"
  echo "    2) standard (faster / fewer 429, ~2x cost)"
  read -rp "  Choice [1-2, default: 1]: " FLEX_CHOICE
  [[ "${FLEX_CHOICE:-1}" == "2" ]] && NOFLEX_FLAG="--no-flex"

  # Two already-generated answer files, judged against each other — no RunPod needed.
  echo ""
  echo "  What should the judge produce?"
  echo "    1) both      — the 0-10 score for two files PLUS the A-vs-B verdict.  4 calls/question"
  echo "    2) pairwise  — the A-vs-B verdict only, no 0-10 score.  2 calls/question"
  echo "       Cannot build a leaderboard column: there is no absolute number."
  echo "    3) pointwise — 0-10 score per question, ONE answer file.  1 judge call/question"
  echo "       This is what a leaderboard column is built from."
  read -rp "  Choice [1-3, default: 1]: " _SCORE_MODE_CHOICE
  case "${_SCORE_MODE_CHOICE:-1}" in
    1) SCORE_MODE="both";      NEED_TWO=true  ;;
    2) SCORE_MODE="pairwise";  NEED_TWO=true  ;;
    3) SCORE_MODE="pointwise"; NEED_TWO=false ;;
    *) echo "Invalid choice"; exit 1 ;;
  esac
  # --score-mode only means anything with two files; one file is pointwise by
  # definition and main.py ignores the flag there.
  MODE_FLAG=""
  [[ "$NEED_TWO" == "true" ]] && MODE_FLAG=" --score-mode $SCORE_MODE"

  echo ""
  echo "  Score a single $([[ "$NEED_TWO" == "true" ]] && echo "pair of files" || echo "file"), or a three-run batch?"
  if [[ "$NEED_TWO" == "true" ]]; then
    echo "    1) single pair"
    echo "    3) three pairs (first / second / third run)"
  else
    echo "    1) single file"
    echo "    3) three files (first / second / third run)"
  fi
  read -rp "  Choice [1/3, default: 1]: " _SCORE_RUNS
  if [[ "${_SCORE_RUNS:-1}" == "3" ]]; then
    for _label in "first-run" "second-run" "third-run"; do
      echo "  --- $_label ---"
      if [[ "$NEED_TWO" == "true" ]]; then
        _fa=$(_read_answer_file "    File A: "); _fa=$(_convert_if_jsonl "$_fa")
        _fb=$(_read_answer_file "    File B: "); _fb=$(_convert_if_jsonl "$_fb")
      else
        _fa=""; _fb=$(_read_answer_file "    Answer file: "); _fb=$(_convert_if_jsonl "$_fb")
      fi
      read -rp "    Output file: " _out
      if [[ "$EXPORT_ON" == "true" ]]; then
        read -rp "    Model A label: " _ma
        read -rp "    Model B label: " _mb
        MODEL_A_LABELS+=("$_ma")
        MODEL_B_LABELS+=("$_mb")
      fi
      SCORE_FLAGS_ARR+=("--score $_fa $_fb$MODE_FLAG")
      OUTPUT_FILES_ARR+=("$_out")
    done
    SCORE_MULTI_RUN=true
  else
    if [[ "$NEED_TWO" == "true" ]]; then
      _fa=$(_read_answer_file "  File A path: ")
      _fb=$(_read_answer_file "  File B path: ")
      _fa=$(_convert_if_jsonl "$_fa")
      _fb=$(_convert_if_jsonl "$_fb")
    else
      _fa=""
      _fb=$(_read_answer_file "  Answer file path: ")
      _fb=$(_convert_if_jsonl "$_fb")
    fi
    SCORE_FLAGS_ARR+=("--score $_fa $_fb$MODE_FLAG")
    SCORE_MULTI_RUN=false
    if [[ "$EXPORT_ON" == "true" ]]; then
      read -rp "  Model A label: " MODEL_A_LABEL
      read -rp "  Model B label: " MODEL_B_LABEL
    fi
    read -rp "  Output file [default: output/scores.json]: " _OUTPUT_FILE
    _OUTPUT_FILE="${_OUTPUT_FILE:-output/scores.json}"
    OUTPUT_BASE="${_OUTPUT_FILE%.json}"
    RUN_SUFFIXES=("")
  fi
  SCORE_FLAG="${SCORE_FLAGS_ARR[0]}"
  NEED_RUNPOD=false
  echo ""
  read -rp "  Number of workers for scoring [default: 1]: " WORKERS
  WORKERS="${WORKERS:-1}"
fi

if [[ "$NEED_RUNPOD" == "true" ]]; then
  echo ""
  echo "=== Select model ==="
  N_MODELS=$(jq 'length' "$MODELS_CONFIG")
  jq -r 'to_entries[] | "  \(.key + 1)) \(.value.label)  [\(.value.provider // "vllm")]"' "$MODELS_CONFIG"
  echo ""
  read -rp "Choice [1-$N_MODELS]: " MODEL_CHOICE

  if ! [[ "$MODEL_CHOICE" =~ ^[0-9]+$ ]] || (( MODEL_CHOICE < 1 || MODEL_CHOICE > N_MODELS )); then
    echo "Invalid choice"; exit 1
  fi
  build_docker_args $((MODEL_CHOICE - 1))

  if [[ "$MODEL_PROVIDER" == "openrouter" ]]; then
    NEED_RUNPOD=false
    require_env OPENROUTER_API_KEY "calling the candidate model on OpenRouter"
    MODE="opencode"
    echo "Model: $MODEL_LABEL — ${MODEL_FLAG#--model }  (no GPU pod needed)"
  else
    require_env RUNPOD_API_KEY "creating the GPU pod"
    require_env HF_TOKEN "pulling the model/LoRA on the pod"
    echo "Model: $MODEL_LABEL"

    echo ""
    echo "=== Select mode ==="
    echo "1) opencode — agent mode; the model can read the project documents (default)"
    echo "2) api      — plain vLLM chat-completions call, question text only"
    read -rp "Choice [1-2]: " MODE_CHOICE
    case "${MODE_CHOICE:-1}" in
      1) MODE="opencode" ;;
      2) MODE="api" ;;
      *) echo "Invalid choice"; exit 1 ;;
    esac
  fi

  if [[ "$MODE" == "opencode" ]]; then
    echo ""
    read -rp "Have the model explore the documents before each question (--explore)? [y/N]: " EXPLORE_CHOICE
    [[ "$(echo "$EXPLORE_CHOICE" | tr '[:upper:]' '[:lower:]')" == "y" ]] && EXPLORE_FLAG="--explore"
  fi

  echo ""
  read -rp "Number of workers [default: 1]: " WORKERS
  WORKERS="${WORKERS:-1}"
fi

if [[ "$SCORE_MULTI_RUN" == "true" ]]; then
  RUN_SUFFIXES=("first-run" "second-run" "third-run")
elif [[ -z "$SCORE_FLAG" ]]; then
  RUN_SUFFIXES=()
  echo ""
  echo "=== Run mode ==="
  echo "1) Single run"
  echo "2) Three runs (first / second / third)"
  read -rp "Choice [1-2, default: 1]: " RUN_MODE_CHOICE
  case "${RUN_MODE_CHOICE:-1}" in
    2)
      read -rp "Output base name (suffix -first/-second/-third-run.json is appended) [default: output/answers]: " OUTPUT_BASE
      OUTPUT_BASE="${OUTPUT_BASE:-output/answers}"
      RUN_SUFFIXES=("first-run" "second-run" "third-run")
      ;;
    *)
      read -rp "Output file [default: output/answers.json]: " _OUTPUT_FILE
      _OUTPUT_FILE="${_OUTPUT_FILE:-output/answers.json}"
      RUN_SUFFIXES=("")
      OUTPUT_BASE="${_OUTPUT_FILE%.json}"
      ;;
  esac
fi

echo ""
echo "=== Summary ==="
echo "  Task:    $([[ "$DO_SCORE" == "true" ]] && echo "score" || echo "generate")"
echo "  Rubric:  ${RUBRIC_FLAG#--rubric }"
[[ "$DO_SCORE" == "true" ]] && echo "  Scoring: $SCORE_MODE — $([[ "$NEED_TWO" == "true" ]] && echo "two answer files" || echo "one answer file")" || true
if [[ "$NEED_RUNPOD" == "true" ]]; then
  echo "  Model:   $MODEL_LABEL"
  echo "  Mode:    $MODE"
  echo "  Explore: $([[ -n "$EXPLORE_FLAG" ]] && echo yes || echo no)"
fi
echo "  Workers: $WORKERS"
if [[ "$SCORE_MULTI_RUN" == "true" ]]; then
  echo "  Output:  ${OUTPUT_FILES_ARR[*]}"
elif [[ ${#RUN_SUFFIXES[@]} -gt 0 && -n "${RUN_SUFFIXES[0]}" ]]; then
  echo "  Output:  ${OUTPUT_BASE}-{first,second,third}-run.json"
else
  echo "  Output:  ${OUTPUT_BASE}.json"
fi
if [[ "$NEED_RUNPOD" == "true" ]]; then
  echo ""
  echo "  A RunPod GPU pod (RTX 6000 Ada) will be created and billed until the run finishes."
fi
read -rp "Proceed? [Y/n]: " CONFIRM_CHOICE
if [[ "$(echo "${CONFIRM_CHOICE:-y}" | tr '[:upper:]' '[:lower:]')" == "n" ]]; then
  echo "Aborted — nothing was created."
  exit 0
fi

cd "$SCRIPT_DIR"
POD_ID=""
MAX_RUN_RETRIES=3

# Safety net: terminate pod on Ctrl+C or unexpected exit
terminate_pod() {
  if [[ -n "${POD_ID:-}" ]]; then
    echo ""
    echo "Terminating RunPod pod $POD_ID..."
    curl -sf -X POST "$RUNPOD_GRAPHQL?api_key=$RUNPOD_API_KEY" \
      -H "Content-Type: application/json" \
      -d "$(jq -nc --arg id "$POD_ID" \
        '{query: "mutation($id: String!) { podTerminate(input: {podId: $id}) }",
          variables: {id: $id}}')" \
      > /dev/null \
      && echo "Pod terminated." \
      || echo "Warning: failed to terminate pod $POD_ID — check RunPod console."
    POD_ID=""
  fi
}
trap terminate_pod EXIT

create_runpod_pod() {
  echo "Creating RunPod pod (RTX 6000 Ada)..."

  POD_ID=""
  CREATE_RETRY=0
  CREATE_MAX_RETRIES=20  # 20 × 30s = ~10 min
  while [[ -z "$POD_ID" ]]; do
    CREATE_RESPONSE=$(curl -sf -X POST "$RUNPOD_GRAPHQL?api_key=$RUNPOD_API_KEY" \
      -H "Content-Type: application/json" \
      -d "$(jq -nc \
        --arg args "$DOCKER_ARGS" \
        --arg hf "$HF_TOKEN" \
        '{
          query: "mutation($i: PodFindAndDeployOnDemandInput!) { podFindAndDeployOnDemand(input: $i) { id } }",
          variables: {
            i: {
              cloudType: "SECURE",
              gpuCount: 1,
              volumeInGb: 50,
              containerDiskInGb: 100,
              minVcpuCount: 8,
              minMemoryInGb: 32,
              gpuTypeId: "NVIDIA RTX 6000 Ada Generation",
              name: "vllm-eval",
              imageName: "vllm/vllm-openai:latest",
              dockerArgs: $args,
              ports: "8000/http",
              volumeMountPath: "/workspace",
              env: [
                {key: "HF_TOKEN", value: $hf},
                {key: "HUGGING_FACE_HUB_TOKEN", value: $hf}
              ]
            }
          }
        }')")

    ERROR_CODE=$(echo "$CREATE_RESPONSE" | jq -r '.errors[0].extensions.code // empty')
    POD_ID=$(echo "$CREATE_RESPONSE" | jq -r '.data.podFindAndDeployOnDemand.id // empty')

    if [[ -n "$POD_ID" ]]; then
      break
    elif [[ "$ERROR_CODE" == "SUPPLY_CONSTRAINT" ]]; then
      CREATE_RETRY=$((CREATE_RETRY + 1))
      if [[ $CREATE_RETRY -gt $CREATE_MAX_RETRIES ]]; then
        echo "No RTX 6000 Ada available after $CREATE_MAX_RETRIES retries. Giving up."
        exit 1
      fi
      echo "  No GPU available (SUPPLY_CONSTRAINT), retrying in 30s... [$CREATE_RETRY/$CREATE_MAX_RETRIES]"
      sleep 30
    else
      echo "RunPod API error:"
      echo "$CREATE_RESPONSE" | jq .
      exit 1
    fi
  done

  echo "Pod created: $POD_ID"
  PROXY_BASE="https://${POD_ID}-8000.proxy.runpod.net"
}

configure_opencode() {
  # Besides the pod URL, make sure the served-model alias is declared in the provider's models map: opencode rejects an undeclared model id with a generic UnknownError before any request is sent, which main.py would only see as an empty answer.
  jq --arg url "$PROXY_BASE/v1" --arg model "$ADAPTER_NAME" \
    '.provider.vllm.options.baseURL = $url
     | .provider.vllm.models[$model] //= {name: $model}' \
    "$OPENCODE_CONFIG" > /tmp/_opencode_cfg.json \
    && mv /tmp/_opencode_cfg.json "$OPENCODE_CONFIG"
  echo "opencode.json → $PROXY_BASE/v1 (model: $ADAPTER_NAME)"

  jq --arg key "sk-${POD_ID}" \
    '.vllm.key = $key' \
    "$OPENCODE_AUTH" > /tmp/_opencode_auth.json \
    && mv /tmp/_opencode_auth.json "$OPENCODE_AUTH"
  echo "auth.json → sk-${POD_ID}"
}

wait_for_vllm_ready() {
  echo ""
  echo "Waiting for vLLM to be ready (model loading may take several minutes)..."
  MAX_ATTEMPTS=60  # 60 × 20s = 20 min max
  for ((i=1; i<=MAX_ATTEMPTS; i++)); do
    if curl -sf --max-time 10 "$PROXY_BASE/health" > /dev/null 2>&1; then
      echo "vLLM is ready!"
      return
    fi
    if [[ $i -eq $MAX_ATTEMPTS ]]; then
      echo "Timed out waiting for vLLM. Check RunPod console for pod: $POD_ID"
      exit 1
    fi
    echo "  [$i/$MAX_ATTEMPTS] not ready, retrying in 20s..."
    sleep 20
  done
}

SUFFIX_IDX=0
for suffix in "${RUN_SUFFIXES[@]}"; do
  if [[ "$SCORE_MULTI_RUN" == "true" ]]; then
    OUTPUT_FILE="${OUTPUT_FILES_ARR[$SUFFIX_IDX]}"
    SCORE_FLAG="${SCORE_FLAGS_ARR[$SUFFIX_IDX]}"
    echo ""
    echo "======================================================"
    echo "=== Run: $suffix"
    echo "======================================================"
  elif [[ -n "$suffix" ]]; then
    OUTPUT_FILE="${OUTPUT_BASE}-${suffix}.json"
    echo ""
    echo "======================================================"
    echo "=== Run: $suffix"
    echo "======================================================"
  else
    OUTPUT_FILE="${OUTPUT_BASE}.json"
  fi
  ERROR_FILE="${OUTPUT_FILE%.*}.errors.json"

  for ((run=1; run<=MAX_RUN_RETRIES; run++)); do
    [[ $run -gt 1 ]] && echo "" && echo "=== Retry $run/$MAX_RUN_RETRIES — creating new pod ==="

  if [[ "$NEED_RUNPOD" == "true" ]]; then
    create_runpod_pod
    configure_opencode
    # For --mode api, main.py talks to vLLM directly (no opencode.json/auth.json involved), so this pod's URL/key must be passed explicitly.
    if [[ "$MODE" == "api" ]]; then
      API_FLAG="--api-url ${PROXY_BASE}/v1/chat/completions --api-key sk-${POD_ID}"
      echo "api mode → ${PROXY_BASE}/v1/chat/completions"
    fi
    wait_for_vllm_ready
  fi

  echo ""
  echo "=== Running main.py | mode: $MODE | explore: $([[ -n "$EXPLORE_FLAG" ]] && echo yes || echo no) | workers: $WORKERS | output: $OUTPUT_FILE ==="
  echo ""
  uv run python main.py --mode "$MODE" $EXPLORE_FLAG --workers "$WORKERS" --output "$OUTPUT_FILE" $SCORE_FLAG ${RUBRIC_FLAG:-} ${NOFLEX_FLAG:-} ${API_FLAG:-} ${MODEL_FLAG:-} "$@"

  [[ "$NEED_RUNPOD" == "true" ]] && terminate_pod

  if [[ ! -f "$ERROR_FILE" ]] || ! python3 -c "import json,sys; d=json.load(open('$ERROR_FILE')); sys.exit(0 if d else 1)" 2>/dev/null; then
    break
  fi

  ERROR_COUNT=$(python3 -c "import json; print(len(json.load(open('$ERROR_FILE'))))" 2>/dev/null || echo "?")
  if [[ $run -lt $MAX_RUN_RETRIES ]]; then
    echo "  $ERROR_COUNT error(s) remain, will retry with a new pod..."
  else
    echo "  [max retries reached] $ERROR_COUNT error(s) remain in $ERROR_FILE"
  fi
  done  # end retry loop
  SUFFIX_IDX=$((SUFFIX_IDX + 1))
done  # end suffix loop

# Export scoring to Google Sheets
if [[ -n "$SCORE_FLAG" && "$(echo "${EXPORT_CHOICE:-}" | tr '[:upper:]' '[:lower:]')" == "y" ]]; then
  echo ""
  if [[ "$SCORE_MULTI_RUN" == "true" ]]; then
    _EXPORT_IDX=0
    for ((_EXPORT_IDX=0; _EXPORT_IDX<3; _EXPORT_IDX++)); do
      uv run python scripts/export_sheets.py scoring \
        --file "${OUTPUT_FILES_ARR[$_EXPORT_IDX]}" \
        --model-a "${MODEL_A_LABELS[$_EXPORT_IDX]}" \
        --model-b "${MODEL_B_LABELS[$_EXPORT_IDX]}" \
        --append
    done
  else
    uv run python scripts/export_sheets.py scoring --file "$OUTPUT_FILE" --model-a "$MODEL_A_LABEL" --model-b "$MODEL_B_LABEL" --append
  fi
fi
