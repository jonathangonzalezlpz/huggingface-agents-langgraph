"""Summarize model trials without publishing questions or reference answers."""

import argparse
from pathlib import Path

from huggingface_agents_langgraph.run_tracking import list_records


def report(group_id: str) -> str:
    records = sorted(
        [
            record
            for record in list_records("experiments")
            if record.get("evaluation_group_id") == group_id
        ],
        key=lambda record: record["created_at"],
    )
    if not records:
        raise ValueError("No model trials found")
    control = records[0]

    def fixed(config: dict) -> dict:
        return {
            key: value
            for key, value in config.items()
            if key not in {"name", "model", "vision_model"}
        }

    comparable = all(
        fixed(record["config"]) == fixed(control["config"]) for record in records
    )
    lines = [
        "# Evaluación local de modelos V3.1",
        "",
        f"Grupo: `{group_id}`. Puntuaciones locales; sin envíos oficiales.",
        "",
        "| Variante | Estado | Aciertos | Media s | Mediana s | P95 s | Errores "
        "| Carga total s | Pico VRAM MiB | RAM disponible mínima MiB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        answers = record["answers"]
        metrics = record.get("metrics", {})
        score = record.get("local_score")
        correct = (
            f"{score['correct_count']}/{score['total_attempted']}"
            if score
            else "pendiente"
        )
        timings = [
            f"{metrics[key]:.1f}" if metrics.get(key) is not None else "—"
            for key in ("mean_seconds", "median_seconds", "p95_seconds")
        ]
        peak = max(
            (
                answer.get("resources", {}).get("gpu_peak_used_mib", 0)
                for answer in answers
            ),
            default=0,
        )
        available = [
            answer["resources"]["minimum_available_ram_mib"]
            for answer in answers
            if answer.get("resources", {}).get("minimum_available_ram_mib") is not None
        ]
        load = sum(answer.get("model_load_seconds", 0) for answer in answers)
        lines.append(
            f"| {record['config']['name']} | {record['status']} "
            f"({len(answers)}/20) | {correct} | {' | '.join(timings)} "
            f"| {metrics.get('technical_errors', 0)} | {load:.1f} | {peak} "
            f"| {min(available) if available else '—'} |"
        )
    lines.extend(
        [
            "",
            "## Configuración y trazabilidad",
            "",
            f"Configuración fija entre variantes: {'sí' if comparable else 'no'}.",
            "",
        ]
    )
    for record in records:
        config = record["config"]
        reasoner = config["model"]["model_id"]
        vision = (config.get("vision_model") or {}).get(
            "model_id", "SmolVLM original en CPU"
        )
        correct = [
            index
            for index, answer in enumerate(record["answers"], 1)
            if answer.get("locally_correct") is True
        ]
        lines.extend(
            [
                f"- `{record['id']}`: {config['name']}. Razonador: `{reasoner}`. "
                f"Visión: `{vision}`. Posiciones acertadas: {correct}."
            ]
        )
        if record.get("local_score") and control.get("local_score"):
            if record.get("task_set_sha256") == control.get("task_set_sha256"):
                previous = {
                    answer["task_id"]: answer.get("locally_correct")
                    for answer in control["answers"]
                }
                gained = [
                    index
                    for index, answer in enumerate(record["answers"], 1)
                    if answer.get("locally_correct") is True
                    and previous.get(answer["task_id"]) is False
                ]
                lost = [
                    index
                    for index, answer in enumerate(record["answers"], 1)
                    if answer.get("locally_correct") is False
                    and previous.get(answer["task_id"]) is True
                ]
                lines.append(
                    f"  Frente al primer control: gana {gained}; pierde {lost}."
                )
    hashes = {
        record.get("source_identity", {}).get("source_sha256") for record in records
    }
    inputs = {record.get("task_set_sha256") for record in records}
    lines.extend(
        [
            "",
            f"Hashes de código: {len(hashes)}; conjuntos de entrada: {len(inputs)}.",
            "",
            "La carga de modelos está incluida en los tiempos de las preguntas "
            "y llamadas LLM. Se informa también por separado. El pico de VRAM "
            "es el máximo muestreado a 1 Hz del dispositivo completo, incluido "
            "escritorio, otros procesos y el modelo anterior durante el cambio; "
            "no es el máximo absoluto ni memoria "
            "exclusiva del agente. La RAM disponible corresponde al sistema.",
            "La media y percentiles incluyen también preguntas con error. "
            "No equivalen a latencia de respuestas correctas ni a tiempo de kernel.",
            "",
            "Una pasada por variante no demuestra significación estadística. "
            "Las fuentes web y cachés de descargas pueden variar con el orden. "
            "No se reutilizan respuestas.",
            "",
            "El control contemporáneo mantiene la misma receta V3.1 "
            "que los candidatos. "
            "No es una reproducción de la V2 histórica ni de la V3 conjunta. "
            "Véase [seleccion-modelos-v3.1.md](seleccion-modelos-v3.1.md).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-id", default="v31-native-models-20261030-r1")
    parser.add_argument("--output", type=Path, default=Path("docs/resultados-v3.1.md"))
    args = parser.parse_args()
    args.output.write_text(report(args.group_id), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
