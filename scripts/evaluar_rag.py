"""Evalúa la recuperación del RAG con preguntas etiquetadas (evals/preguntas_rag.jsonl).

Métricas:
- hit@k: proporción de preguntas en que al menos un fragmento esperado aparece en el top-k.
- MRR: promedio de 1/posición del primer fragmento esperado (1.0 = siempre en primer lugar).
- Rechazo fuera de alcance: proporción de preguntas sin fragmentos esperados para las que el
  recuperador no devolvió nada por encima del umbral (lo deseable es 100%).

Uso (requiere haber corrido la ingesta):
    python -m scripts.evaluar_rag
    python -m scripts.evaluar_rag --umbral 0.4 --k 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.rag.embeddings import FastEmbedEmbedder
from app.rag.retriever import Recuperador
from app.rag.store import IndiceVectorial

RUTA_PREGUNTAS = Path(__file__).resolve().parent.parent / "evals" / "preguntas_rag.jsonl"


def coincide(id_recuperado: str, esperado: str) -> bool:
    # "lft-art132" también acepta las partes "lft-art132-p1", "lft-art132-p2"...
    return id_recuperado == esperado or id_recuperado.startswith(esperado + "-p")


def main() -> None:
    parser = argparse.ArgumentParser()
    ajustes = get_settings()
    parser.add_argument("--k", type=int, default=ajustes.rag_top_k)
    parser.add_argument("--umbral", type=float, default=ajustes.rag_min_score)
    args = parser.parse_args()

    recuperador = Recuperador(
        IndiceVectorial.cargar(ajustes.index_dir),
        FastEmbedEmbedder(ajustes.embedding_model),
        top_k=args.k,
        min_score=args.umbral,
    )
    casos = [json.loads(linea) for linea in RUTA_PREGUNTAS.read_text(encoding="utf-8").splitlines()]
    aciertos, rr, en_alcance, rechazos, fuera = 0, 0.0, 0, 0, 0
    for caso in casos:
        resultados = recuperador.buscar(caso["pregunta"])
        ids = [r.id for r in resultados]
        if not caso["esperados"]:
            fuera += 1
            rechazos += not ids
            estado = "OK (rechazada)" if not ids else f"FALLO: devolvió {ids[:3]}"
        else:
            en_alcance += 1
            posicion = next(
                (i for i, x in enumerate(ids, 1) if any(coincide(x, e) for e in caso["esperados"])),
                None,
            )
            if posicion:
                aciertos += 1
                rr += 1 / posicion
            estado = f"OK (posición {posicion})" if posicion else f"FALLO: {ids[:3]}"
        print(f"- {caso['pregunta'][:60]:<60} {estado}")

    print(f"\nk={args.k} umbral={args.umbral}")
    print(f"hit@{args.k}: {aciertos}/{en_alcance} = {aciertos / max(en_alcance, 1):.2f}")
    print(f"MRR: {rr / max(en_alcance, 1):.2f}")
    print(f"Rechazo fuera de alcance: {rechazos}/{fuera} = {rechazos / max(fuera, 1):.2f}")


if __name__ == "__main__":
    main()
