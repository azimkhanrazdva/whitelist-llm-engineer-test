import argparse
import json
import sys
from pathlib import Path

from .eval import evaluate_directory
from .extractor import extract_document
from .llm import OllamaClient


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Conservative document extraction CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Document text")
    group.add_argument("--input", type=Path, help="UTF-8 text file")
    group.add_argument("--eval", dest="eval_dir", type=Path, help="Directory with .txt/.json cases")
    parser.add_argument("--ollama-model", help="Use a local Ollama model instead of the offline rules backend")
    args = parser.parse_args(argv)
    if args.eval_dir:
        print(json.dumps(evaluate_directory(args.eval_dir), ensure_ascii=False, indent=2))
        return 0
    text = args.text if args.text is not None else args.input.read_text(encoding="utf-8")
    result = OllamaClient(model=args.ollama_model).extract(text) if args.ollama_model else extract_document(text)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
