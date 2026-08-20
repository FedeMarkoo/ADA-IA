"""Dataset preparation and explicit LoRA fine-tuning helpers."""

import json
from pathlib import Path


def _read(path):
    source = Path(path).expanduser()
    rows = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL inválido en línea {line_number}: {exc}") from exc
        rows.append(item)
    return rows


def validate_dataset(path):
    rows = _read(path)
    if not rows:
        raise ValueError("El dataset no contiene ejemplos.")
    tasks: dict = {}
    for index, item in enumerate(rows, 1):
        if not isinstance(item, dict) or not item.get("prompt") or not item.get("response"):
            raise ValueError(f"El ejemplo {index} necesita prompt y response.")
        task = str(item.get("task") or "general")
        tasks[task] = tasks.get(task, 0) + 1
    return {"ok": True, "examples": len(rows), "tasks": tasks}


def prepare_dataset(input_path, output_path):
    """Convert evaluation JSON/JSONL cases into safe chat-training JSONL."""
    source = Path(input_path).expanduser()
    if source.suffix.lower() == ".json":
        cases = json.loads(source.read_text(encoding="utf-8"))
    else:
        cases = _read(source)
    if not isinstance(cases, list):
        raise ValueError("La fuente debe ser una lista JSON o JSONL.")
    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for case in cases:
            prompt = case.get("prompt") or case.get("input")
            response = case.get("response") or case.get("expected")
            if not prompt or not response:
                continue
            row = {
                "task": case.get("task") or case.get("expected_action") or "general",
                "prompt": str(prompt),
                "response": str(response),
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return validate_dataset(target)


def train_lora(dataset_path, model_name, output_dir, max_steps=100):
    """Run an explicit local LoRA training job when the fine-tuning extra is installed."""
    validate_dataset(dataset_path)
    try:
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    except ImportError as exc:
        raise RuntimeError("Instalá la extra de fine-tuning: pip install -e '.[fine-tuning]'") from exc

    rows = _read(dataset_path)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    dataset = Dataset.from_list([{"text": f"Usuario: {row['prompt']}\nADA: {row['response']}"} for row in rows])
    tokenized = dataset.map(
        lambda batch: tokenizer(batch["text"], truncation=True, padding="max_length", max_length=512), batched=True
    )
    tokenized = tokenized.map(lambda batch: {"labels": list(batch["input_ids"])}, batched=True)
    trainer = Trainer(
        model=model,
        train_dataset=tokenized,
        args=TrainingArguments(
            output_dir=str(Path(output_dir).expanduser()),
            max_steps=int(max_steps),
            per_device_train_batch_size=1,
            logging_steps=max(1, min(10, int(max_steps))),
            save_strategy="steps",
            save_steps=max(1, int(max_steps)),
            report_to=[],
        ),
    )
    trainer.train()
    trainer.save_model(str(Path(output_dir).expanduser()))
    tokenizer.save_pretrained(str(Path(output_dir).expanduser()))
    return {"ok": True, "output_dir": str(Path(output_dir).expanduser()), "examples": len(rows)}
