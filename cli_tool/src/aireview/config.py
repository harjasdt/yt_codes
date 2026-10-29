"""One place for the numbers that must agree with each other."""
NUM_CTX = 16_384          # tokens Ollama allocates for each request
NUM_PREDICT = 2_048       # hard cap on reply length, so a rambling model cannot run for minutes
REQUEST_TIMEOUT = 120     # seconds to wait for one model call

RESERVED_TOKENS = 4_096   # room for system prompt + findings + the reply
CHARS_PER_TOKEN = 2.5     # conservative; code averages about 3
MAX_DIFF_CHARS = int((NUM_CTX - RESERVED_TOKENS) * CHARS_PER_TOKEN)  # whole diff budget, derived from NUM_CTX
PER_FILE_CHARS = 3_000    # one big file must not hide the rest
MAX_NEW_FILE_BYTES = 100_000
