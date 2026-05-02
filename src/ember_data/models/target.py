"""Target domain model."""

from enum import StrEnum

from pydantic import BaseModel, Field


class TargetType(StrEnum):
    """Classification of biological target."""

    GENE = "gene"
    PROTEIN = "protein"
    PATHWAY = "pathway"


class Target(BaseModel):
    """A biological target - protein, gene, or pathway."""

    id: str
    name: str
    type: TargetType
    organism: str
    aliases: list[str] = Field(default_factory=list)
    gene_id: str | None = None
    uniprot_id: str | None = None
