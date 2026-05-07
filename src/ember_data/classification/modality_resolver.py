"""ModalityResolver — enum-based resolver for drug modality and cell line classification."""

from __future__ import annotations

from ember_data.classification.enums import CellLineClass, ModalityClassification
from ember_data.classification.resolver import ClassificationResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm

# ---------------------------------------------------------------------------
# Synonym tables
# ---------------------------------------------------------------------------

# Maps lowercase synonym → ModalityClassification enum value
_MODALITY_SYNONYMS: dict[str, ModalityClassification] = {
    # mAb / monoclonal antibody
    "mab": ModalityClassification.MAB,
    "monoclonal antibody": ModalityClassification.MONOCLONAL_ANTIBODY,
    "monoclonal antibodies": ModalityClassification.MONOCLONAL_ANTIBODY,
    "monospecific antibody": ModalityClassification.MONOCLONAL_ANTIBODY,
    # bispecific
    "bispecific": ModalityClassification.BISPECIFIC,
    "bispecific antibody": ModalityClassification.BISPECIFIC_ANTIBODY,
    "bispecific antibodies": ModalityClassification.BISPECIFIC_ANTIBODY,
    "bsab": ModalityClassification.BISPECIFIC_ANTIBODY,
    "bsabs": ModalityClassification.BISPECIFIC_ANTIBODY,
    "bispecific mab": ModalityClassification.BISPECIFIC_ANTIBODY,
    "bispecific monoclonal antibody": ModalityClassification.BISPECIFIC_ANTIBODY,
    # ADC
    "adc": ModalityClassification.ADC,
    "antibody drug conjugate": ModalityClassification.ADC,
    "antibody-drug conjugate": ModalityClassification.ADC,
    "antibody drug conjugates": ModalityClassification.ADC,
    "antibody-drug conjugates": ModalityClassification.ADC,
    # Fc-fusion
    "fc fusion": ModalityClassification.FC_FUSION,
    "fc-fusion": ModalityClassification.FC_FUSION,
    "fc fusion protein": ModalityClassification.FC_FUSION,
    "fc-fusion protein": ModalityClassification.FC_FUSION,
    "fusion protein": ModalityClassification.FC_FUSION,
    # small molecule
    "small molecule": ModalityClassification.SMALL_MOLECULE,
    "small molecules": ModalityClassification.SMALL_MOLECULE,
    "smi": ModalityClassification.SMALL_MOLECULE,
    # cell therapy
    "cell therapy": ModalityClassification.CELL_THERAPY,
    "car-t": ModalityClassification.CELL_THERAPY,
    "car t": ModalityClassification.CELL_THERAPY,
    "cart": ModalityClassification.CELL_THERAPY,
    # gene therapy
    "gene therapy": ModalityClassification.GENE_THERAPY,
    # rna therapy
    "rna therapy": ModalityClassification.RNA_THERAPY,
    "sirna": ModalityClassification.RNA_THERAPY,
    "mrna": ModalityClassification.RNA_THERAPY,
    "antisense": ModalityClassification.RNA_THERAPY,
    # peptide
    "peptide": ModalityClassification.PEPTIDE,
    "peptides": ModalityClassification.PEPTIDE,
    # protein
    "protein": ModalityClassification.PROTEIN,
    "recombinant protein": ModalityClassification.PROTEIN,
    # oligonucleotide
    "oligonucleotide": ModalityClassification.OLIGONUCLEOTIDE,
    "oligonucleotides": ModalityClassification.OLIGONUCLEOTIDE,
    "aso": ModalityClassification.OLIGONUCLEOTIDE,
    # vaccine
    "vaccine": ModalityClassification.VACCINE,
    "vaccines": ModalityClassification.VACCINE,
    # radiopharmaceutical
    "radiopharmaceutical": ModalityClassification.RADIOPHARMACEUTICAL,
    "radiopharmaceuticals": ModalityClassification.RADIOPHARMACEUTICAL,
    # unknown
    "unknown": ModalityClassification.UNKNOWN,
}

# Maps ModalityClassification → canonical label
_MODALITY_LABELS: dict[ModalityClassification, str] = {
    ModalityClassification.SMALL_MOLECULE: "Small Molecule",
    ModalityClassification.MAB: "Monoclonal Antibody (mAb)",
    ModalityClassification.MONOCLONAL_ANTIBODY: "Monoclonal Antibody",
    ModalityClassification.BISPECIFIC: "Bispecific",
    ModalityClassification.BISPECIFIC_ANTIBODY: "Bispecific Antibody",
    ModalityClassification.ADC: "Antibody-Drug Conjugate (ADC)",
    ModalityClassification.FC_FUSION: "Fc-Fusion Protein",
    ModalityClassification.CELL_THERAPY: "Cell Therapy",
    ModalityClassification.GENE_THERAPY: "Gene Therapy",
    ModalityClassification.RNA_THERAPY: "RNA Therapy",
    ModalityClassification.PEPTIDE: "Peptide",
    ModalityClassification.PROTEIN: "Recombinant Protein",
    ModalityClassification.OLIGONUCLEOTIDE: "Oligonucleotide",
    ModalityClassification.VACCINE: "Vaccine",
    ModalityClassification.RADIOPHARMACEUTICAL: "Radiopharmaceutical",
    ModalityClassification.UNKNOWN: "Unknown Modality",
}

# Rough number of approved/investigational drugs per modality category
_MODALITY_COUNT_ESTIMATES: dict[ModalityClassification, int] = {
    ModalityClassification.SMALL_MOLECULE: 10000,
    ModalityClassification.MAB: 200,
    ModalityClassification.MONOCLONAL_ANTIBODY: 200,
    ModalityClassification.BISPECIFIC: 30,
    ModalityClassification.BISPECIFIC_ANTIBODY: 30,
    ModalityClassification.ADC: 25,
    ModalityClassification.FC_FUSION: 20,
    ModalityClassification.CELL_THERAPY: 15,
    ModalityClassification.GENE_THERAPY: 10,
    ModalityClassification.RNA_THERAPY: 40,
    ModalityClassification.PEPTIDE: 500,
    ModalityClassification.PROTEIN: 300,
    ModalityClassification.OLIGONUCLEOTIDE: 20,
    ModalityClassification.VACCINE: 150,
    ModalityClassification.RADIOPHARMACEUTICAL: 50,
    ModalityClassification.UNKNOWN: 0,
}

# ---------------------------------------------------------------------------

# Maps lowercase synonym → CellLineClass enum value
_CELL_LINE_SYNONYMS: dict[str, CellLineClass] = {
    # mammalian
    "mammalian": CellLineClass.MAMMALIAN,
    "mammalian cell": CellLineClass.MAMMALIAN,
    "mammalian cells": CellLineClass.MAMMALIAN,
    "cho": CellLineClass.MAMMALIAN,
    "chinese hamster ovary": CellLineClass.MAMMALIAN,
    "hek293": CellLineClass.MAMMALIAN,
    "hek 293": CellLineClass.MAMMALIAN,
    "ns0": CellLineClass.MAMMALIAN,
    "sp2/0": CellLineClass.MAMMALIAN,
    # microbial
    "microbial": CellLineClass.MICROBIAL,
    "microbial cell": CellLineClass.MICROBIAL,
    "microbial cells": CellLineClass.MICROBIAL,
    "e. coli": CellLineClass.MICROBIAL,
    "ecoli": CellLineClass.MICROBIAL,
    "escherichia coli": CellLineClass.MICROBIAL,
    "bacterial expression": CellLineClass.MICROBIAL,
    # insect
    "insect": CellLineClass.INSECT,
    "insect cell": CellLineClass.INSECT,
    "insect cells": CellLineClass.INSECT,
    "sf9": CellLineClass.INSECT,
    "sf21": CellLineClass.INSECT,
    "baculovirus": CellLineClass.INSECT,
    "hi5": CellLineClass.INSECT,
    # yeast
    "yeast": CellLineClass.YEAST,
    "pichia": CellLineClass.YEAST,
    "pichia pastoris": CellLineClass.YEAST,
    "saccharomyces": CellLineClass.YEAST,
    # bacterial
    "bacterial": CellLineClass.BACTERIAL,
    "bacteria": CellLineClass.BACTERIAL,
    # human primary
    "human primary": CellLineClass.HUMAN_PRIMARY,
    "primary human": CellLineClass.HUMAN_PRIMARY,
    "primary cells": CellLineClass.HUMAN_PRIMARY,
    # human immortalized
    "human immortalized": CellLineClass.HUMAN_IMMORTALIZED,
    "immortalized": CellLineClass.HUMAN_IMMORTALIZED,
    "hela": CellLineClass.HUMAN_IMMORTALIZED,
    "jurkat": CellLineClass.HUMAN_IMMORTALIZED,
    # murine
    "murine": CellLineClass.MURINE,
    "mouse": CellLineClass.MURINE,
    "3t3": CellLineClass.MURINE,
    # non-human primate
    "non human primate": CellLineClass.NON_HUMAN_PRIMATE,
    "non-human primate": CellLineClass.NON_HUMAN_PRIMATE,
    "nhp": CellLineClass.NON_HUMAN_PRIMATE,
    "vero": CellLineClass.NON_HUMAN_PRIMATE,
    # stem cell derived
    "stem cell": CellLineClass.STEM_CELL_DERIVED,
    "stem cell derived": CellLineClass.STEM_CELL_DERIVED,
    "ipsc": CellLineClass.STEM_CELL_DERIVED,
    "induced pluripotent": CellLineClass.STEM_CELL_DERIVED,
    # organoid
    "organoid": CellLineClass.ORGANOID,
    "organoids": CellLineClass.ORGANOID,
    # other
    "other": CellLineClass.OTHER,
    # unknown
    "unknown": CellLineClass.UNKNOWN,
}

# Maps CellLineClass → canonical label
_CELL_LINE_LABELS: dict[CellLineClass, str] = {
    CellLineClass.MAMMALIAN: "Mammalian",
    CellLineClass.MICROBIAL: "Microbial",
    CellLineClass.HUMAN_PRIMARY: "Human Primary",
    CellLineClass.HUMAN_IMMORTALIZED: "Human Immortalized",
    CellLineClass.MURINE: "Murine",
    CellLineClass.NON_HUMAN_PRIMATE: "Non-Human Primate",
    CellLineClass.INSECT: "Insect",
    CellLineClass.YEAST: "Yeast",
    CellLineClass.BACTERIAL: "Bacterial",
    CellLineClass.STEM_CELL_DERIVED: "Stem Cell-Derived",
    CellLineClass.ORGANOID: "Organoid",
    CellLineClass.OTHER: "Other",
    CellLineClass.UNKNOWN: "Unknown",
}

_CELL_LINE_COUNT_ESTIMATES: dict[CellLineClass, int] = {
    CellLineClass.MAMMALIAN: 500,
    CellLineClass.MICROBIAL: 300,
    CellLineClass.HUMAN_PRIMARY: 100,
    CellLineClass.HUMAN_IMMORTALIZED: 150,
    CellLineClass.MURINE: 200,
    CellLineClass.NON_HUMAN_PRIMATE: 50,
    CellLineClass.INSECT: 80,
    CellLineClass.YEAST: 120,
    CellLineClass.BACTERIAL: 200,
    CellLineClass.STEM_CELL_DERIVED: 40,
    CellLineClass.ORGANOID: 20,
    CellLineClass.OTHER: 50,
    CellLineClass.UNKNOWN: 0,
}


def _synonyms_for_modality(value: ModalityClassification) -> list[str]:
    return [k for k, v in _MODALITY_SYNONYMS.items() if v == value]


def _synonyms_for_cell_line(value: CellLineClass) -> list[str]:
    return [k for k, v in _CELL_LINE_SYNONYMS.items() if v == value]


class ModalityResolver(ClassificationResolver):
    """Resolves free-text inputs to drug modality or cell line class terms.

    Both ``ModalityClassification`` and ``CellLineClass`` enums are supported
    in a single resolver.  Results carry taxonomy ``"Modality"`` or
    ``"CellLineClass"`` respectively.

    Resolution strategy
    -------------------
    1. Exact synonym/name match (case-insensitive) → confidence 1.0
    2. Partial / substring match → confidence 0.8, scaled by word overlap.

    Results are sorted highest-confidence first.  The flat enum structure
    means ``narrow()`` and ``broaden()`` always return empty lists.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _modality_to_term(
        self, value: ModalityClassification, confidence: float = 1.0
    ) -> ResolvedTerm:
        return ResolvedTerm(
            taxonomy="Modality",
            identifier=value.value,
            label=_MODALITY_LABELS[value],
            confidence=confidence,
            synonyms=_synonyms_for_modality(value),
            parent_id=None,
        )

    def _cell_line_to_term(
        self, value: CellLineClass, confidence: float = 1.0
    ) -> ResolvedTerm:
        return ResolvedTerm(
            taxonomy="CellLineClass",
            identifier=value.value,
            label=_CELL_LINE_LABELS[value],
            confidence=confidence,
            synonyms=_synonyms_for_cell_line(value),
            parent_id=None,
        )

    # ------------------------------------------------------------------
    # ClassificationResolver interface
    # ------------------------------------------------------------------

    def resolve(self, raw_input: str) -> list[ResolvedTerm]:
        """Resolve *raw_input* to modality or cell-line terms, highest confidence first.

        Searches both the ``ModalityClassification`` and ``CellLineClass``
        synonym tables.  Exact matches score 1.0; substring matches score 0.8+.
        """
        query = raw_input.strip().lower()
        if not query:
            return []

        # code (identifier) → best (confidence, term)
        results: dict[str, tuple[float, ResolvedTerm]] = {}

        def _update(identifier: str, confidence: float, term: ResolvedTerm) -> None:
            existing = results.get(identifier)
            if existing is None or confidence > existing[0]:
                results[identifier] = (confidence, term)

        # --- Modality exact matches ---
        if query in _MODALITY_SYNONYMS:
            value = _MODALITY_SYNONYMS[query]
            _update(value.value, 1.0, self._modality_to_term(value, 1.0))

        for value in ModalityClassification:
            if value.value == query:
                _update(value.value, 1.0, self._modality_to_term(value, 1.0))

        # --- CellLineClass exact matches ---
        if query in _CELL_LINE_SYNONYMS:
            value = _CELL_LINE_SYNONYMS[query]
            _update(
                f"cl:{value.value}", 1.0, self._cell_line_to_term(value, 1.0)
            )

        for value in CellLineClass:
            if value.value == query:
                _update(
                    f"cl:{value.value}", 1.0, self._cell_line_to_term(value, 1.0)
                )

        # --- Partial matches (only when no exact hits found) ---
        if not results:
            query_words = set(query.split())

            for synonym, mod_value in _MODALITY_SYNONYMS.items():
                if query in synonym or synonym in query:
                    syn_words = set(synonym.split())
                    overlap = len(query_words & syn_words)
                    total = max(len(query_words), len(syn_words))
                    score = 0.8 + 0.15 * (overlap / total if total else 0)
                    term = self._modality_to_term(mod_value, round(score, 4))
                    _update(mod_value.value, round(score, 4), term)

            for synonym, cl_value in _CELL_LINE_SYNONYMS.items():
                if query in synonym or synonym in query:
                    syn_words = set(synonym.split())
                    overlap = len(query_words & syn_words)
                    total = max(len(query_words), len(syn_words))
                    score = 0.8 + 0.15 * (overlap / total if total else 0)
                    term = self._cell_line_to_term(cl_value, round(score, 4))
                    _update(f"cl:{cl_value.value}", round(score, 4), term)

        if not results:
            return []

        terms = [term for _, term in results.values()]
        terms.sort(key=lambda t: (-t.confidence, t.taxonomy, t.identifier))
        return terms

    def narrow(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return child terms — always empty for flat enum taxonomies."""
        return []

    def broaden(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return parent terms — always empty for flat enum taxonomies."""
        return []

    def disambiguate(
        self, candidates: list[ResolvedTerm]
    ) -> DisambiguationRequest | None:
        """Return a :class:`DisambiguationRequest` when multiple candidates exist.

        Returns ``None`` if zero or one candidate is provided.
        """
        if len(candidates) <= 1:
            return None
        return DisambiguationRequest(
            raw_input="",
            options=candidates,
            rationale=(
                f"Multiple modality/cell-line terms matched ({len(candidates)} candidates). "
                "Please select the intended classification."
            ),
        )

    def estimate_count(self, term: ResolvedTerm) -> int:
        """Return an approximate number of records matching *term*.

        Looks up pre-defined estimates per modality or cell-line class value.
        Returns 0 for unrecognised identifiers.
        """
        if term.taxonomy == "Modality":
            try:
                value = ModalityClassification(term.identifier)
                return _MODALITY_COUNT_ESTIMATES.get(value, 0)
            except ValueError:
                return 0
        if term.taxonomy == "CellLineClass":
            try:
                value = CellLineClass(term.identifier)
                return _CELL_LINE_COUNT_ESTIMATES.get(value, 0)
            except ValueError:
                return 0
        return 0
