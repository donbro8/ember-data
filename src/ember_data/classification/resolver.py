"""ClassificationResolver — abstract base class for all taxonomy resolvers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm


class ClassificationResolver(ABC):
    """Abstract interface for resolving free-text inputs to taxonomy terms.

    Each concrete resolver handles one classification dimension (e.g. ATC for
    drugs, MeSH for indications, UniProt/GO for targets).  All resolvers share
    this contract so the classification pipeline can treat them uniformly.
    """

    @abstractmethod
    def resolve(self, raw_input: str) -> list[ResolvedTerm]:
        """Resolve *raw_input* to one or more ranked taxonomy terms.

        Returns an ordered list of candidates (highest-confidence first).
        Returns an empty list when no match can be found.
        When multiple plausible terms exist, callers should surface a
        :class:`~ember_data.classification.spec.DisambiguationRequest`.
        """

    @abstractmethod
    def narrow(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return child terms that are more specific than *term*.

        For example, narrowing an ATC level-3 node returns its level-4
        chemical-subgroup children.
        """

    @abstractmethod
    def broaden(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return parent terms that are less specific than *term*.

        For example, broadening ATC L04AB04 returns L04AB (the parent group).
        """

    @abstractmethod
    def disambiguate(self, candidates: list[ResolvedTerm]) -> DisambiguationRequest | None:
        """Build a closed-option disambiguation request for ambiguous candidates.

        Returns ``None`` when the candidates are sufficiently distinct or when
        no human-facing disambiguation is needed.
        """

    @abstractmethod
    def estimate_count(self, term: ResolvedTerm) -> int:
        """Estimate the number of data-source records that match *term*.

        The estimate need not be exact; it is used for result-count hints
        and to guide query-narrowing / broadening decisions.
        """
