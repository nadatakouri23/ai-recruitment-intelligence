"""Génère les CV synthétiques d'exemple et compare l'analyse à la vérité terrain.

Usage, depuis la racine du projet :
    backend\\.venv\\Scripts\\python.exe scripts\\generate_sample_cvs.py

Écrit dans data/samples/cvs/ (CV fictifs, sans aucune donnée réelle) puis affiche, pour chaque CV,
la précision et le rappel des compétences détectées. Ce sont des chiffres de RÉGRESSION sur des CV
écrits par nous : ils ne prédisent pas la performance sur de vrais CV.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.candidates.parsing.parser import parse_cv  # noqa: E402
from app.modules.candidates.parsing.text_cleaning import clean_text  # noqa: E402
from app.modules.documents.extraction import detect_kind, extract_text  # noqa: E402
from tests.cv_factory import SYNTHETIC_CVS, render  # noqa: E402

OUTPUT = ROOT / "data" / "samples" / "cvs"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    total_tp = total_found = total_truth = 0
    print(f"{'CV':24s} {'compétences':>12s} {'précision':>10s} {'rappel':>7s}  manquées / en trop")
    for cv in SYNTHETIC_CVS:
        content = render(cv)
        (OUTPUT / cv.filename).write_bytes(content)

        kind = detect_kind(cv.filename, content, 5 * 1024 * 1024)
        text = clean_text(extract_text(content, kind, max_pages=30).text)
        profile = parse_cv(text, today=date(2026, 11, 11))

        found = {s.name for s in profile.skills}
        truth = set(cv.truth.skills)
        true_positives = len(found & truth)
        precision = true_positives / len(found) if found else 1.0
        recall = true_positives / len(truth) if truth else 1.0
        total_tp += true_positives
        total_found += len(found)
        total_truth += len(truth)
        print(
            f"{cv.filename:24s} {len(found):>5d}/{len(truth):<6d} {precision:>10.2f} {recall:>7.2f}"
            f"  manquées={sorted(truth - found)} en_trop={sorted(found - truth)}"
        )

    print(
        f"\nGlobal : précision {total_tp / total_found:.2f} | rappel {total_tp / total_truth:.2f} "
        f"sur {len(SYNTHETIC_CVS)} CV synthétiques -> {OUTPUT}"
    )


if __name__ == "__main__":
    main()
