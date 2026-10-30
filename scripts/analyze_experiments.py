"""Write an aggregate ablation report without publishing benchmark answers."""

import argparse
import json
from collections import Counter
from pathlib import Path

from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID
from huggingface_agents_langgraph.run_tracking import list_records, read_record


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
        raise ValueError("No experiments were found for this evaluation group")
    reference = read_record("experiments", V2_REFERENCE_ID)
    baseline = next(
        (record for record in records if record["config"]["pipeline_version"] == "2"),
        reference,
    )
    baseline_answers = {answer["task_id"]: answer for answer in baseline["answers"]}
    task_order = {
        answer["task_id"]: index for index, answer in enumerate(reference["answers"], 1)
    }
    lines = [
        "# Evaluación de componentes V3",
        "",
        f"Grupo: `{group_id}`. Todas las puntuaciones de esta serie son locales; "
        "no se han realizado envíos oficiales.",
        "",
        "La referencia V2 histórica conserva 6/20 (30 %) y 47,3 segundos de media. "
        "Las variantes se comparan también con un control V2 contemporáneo.",
        "",
        "| Variante | Estado | Aciertos | Media (s) | Mediana (s) | P95 (s) "
        "| Errores técnicos |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for record in records:
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
        lines.append(
            f"| {record['config']['name']} | {record.get('status', 'sin estado')} "
            f"| {correct} | {' | '.join(timings)} "
            f"| {metrics.get('technical_errors', '—')} |"
        )
    lines.extend(
        [
            "",
            "## Comparación por pregunta frente al control",
            "",
            "Los números identifican el orden de las veinte preguntas conservadas. "
            "No se publican preguntas, respuestas de referencia ni credenciales.",
            "",
        ]
    )
    for record in records:
        if record["id"] == baseline["id"]:
            continue
        gained, lost, changed = [], [], []
        for answer in record["answers"]:
            previous = baseline_answers.get(answer["task_id"])
            if not previous:
                continue
            number = task_order[answer["task_id"]]
            if (answer["question"], answer.get("file_name", "")) != (
                previous["question"],
                previous.get("file_name", ""),
            ):
                changed.append(number)
                continue
            if (
                answer.get("locally_correct") is True
                and previous.get("locally_correct") is False
            ):
                gained.append(number)
            if (
                answer.get("locally_correct") is False
                and previous.get("locally_correct") is True
            ):
                lost.append(number)
        lines.extend(
            [
                f"### {record['config']['name']}",
                "",
                f"Experimento: `{record['id']}`.",
                "",
                f"Aciertos ganados: {gained or 'ninguno medido'}. "
                f"Aciertos perdidos: {lost or 'ninguno medido'}. "
                f"Entradas diferentes: {changed or 'ninguna'}.",
                "",
            ]
        )
        answers = record["answers"]
        calls = sum(answer.get("llm_calls", 0) for answer in answers)
        truncated = sum(answer.get("truncated_calls", 0) for answer in answers)
        tokens = sum(answer.get("completion_tokens", 0) for answer in answers)
        stages = Counter()
        for answer in answers:
            stages.update(answer.get("stage_seconds", {}))
        lines.extend(
            [
                f"Llamadas LLM: {calls}; truncamientos: {truncated}; "
                f"tokens de salida comunicados: {tokens}.",
                "",
                "Etapas con mayor tiempo acumulado: "
                + "; ".join(
                    f"`{name}` {seconds:.1f} s"
                    for name, seconds in stages.most_common(3)
                )
                + ".",
                "",
            ]
        )
    hashes = {
        record.get("source_identity", {}).get("source_sha256") for record in records
    }
    question_hashes = {record.get("task_set_sha256") for record in records}
    lines.extend(
        [
            "## Condiciones y límites",
            "",
            f"Hashes de código presentes: {len(hashes)}. "
            f"Conjuntos de entrada presentes: {len(question_hashes)}.",
            "",
            "Se conserva el mismo modelo y capacidades y se ejecutan las variantes en "
            "serie. Los pesos y adjuntos pueden estar en caché; "
            "no se reutilizan respuestas de otra variante. "
            "El razonamiento usa muestreo y las fuentes externas pueden cambiar. "
            "Una repetición por variante no demuestra significación estadística "
            "ni permite separar todo el efecto del orden y las cachés.",
            "",
            "Los cambios de nombre no alteran la configuración ni respuestas de la "
            "referencia histórica. Las trazas y respuestas completas permanecen en el "
            "historial local del panel.",
            "",
            "La interpretación y las decisiones de cierre están en "
            "[evolucion-pipeline.md](evolucion-pipeline.md).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/resultados-v3.md"))
    args = parser.parse_args()
    args.output.write_text(report(args.group_id), encoding="utf-8")
    print(json.dumps({"report": str(args.output)}))


if __name__ == "__main__":
    main()
