"""Taxonomy enums for biotech classification."""

from enum import StrEnum


class Jurisdiction(StrEnum):
    """Regulatory jurisdiction for patents, trials, and approvals."""

    US = "US"
    EU = "EU"
    JP = "JP"
    CN = "CN"
    CA = "CA"
    AU = "AU"
    GB = "GB"
    IN = "IN"
    BR = "BR"
    KR = "KR"
    WIPO = "WIPO"


class CellLineClass(StrEnum):
    """Classification of cell line origin and type."""

    MAMMALIAN = "mammalian"
    CHO = "cho"  # Chinese Hamster Ovary — primary mammalian mfg cell line
    HEK = "hek"  # Human Embryonic Kidney — common expression system
    MICROBIAL = "microbial"
    E_COLI = "e_coli"  # Escherichia coli — dominant bacterial expression host
    YEAST = "yeast"
    PLANT = "plant"
    INSECT = "insect"
    HUMAN_PRIMARY = "human_primary"
    HUMAN_IMMORTALIZED = "human_immortalized"
    MURINE = "murine"
    NON_HUMAN_PRIMATE = "non_human_primate"
    BACTERIAL = "bacterial"
    STEM_CELL_DERIVED = "stem_cell_derived"
    ORGANOID = "organoid"
    OTHER = "other"
    UNKNOWN = "unknown"


class ModalityClassification(StrEnum):
    """Therapeutic modality classification."""

    SMALL_MOLECULE = "small_molecule"
    MAB = "mab"
    MONOCLONAL_ANTIBODY = "monoclonal_antibody"
    BISPECIFIC = "bispecific"
    BISPECIFIC_ANTIBODY = "bispecific_antibody"
    ADC = "adc"
    FC_FUSION = "fc_fusion"
    CELL_THERAPY = "cell_therapy"
    GENE_THERAPY = "gene_therapy"
    RNA_THERAPY = "rna_therapy"
    PEPTIDE = "peptide"
    PROTEIN = "protein"
    OLIGONUCLEOTIDE = "oligonucleotide"
    VACCINE = "vaccine"
    RADIOPHARMACEUTICAL = "radiopharmaceutical"
    UNKNOWN = "unknown"


class ATCNode(StrEnum):
    """Anatomical Therapeutic Chemical (ATC) classification nodes (level 1)."""

    A = "A"  # Alimentary tract and metabolism
    B = "B"  # Blood and blood forming organs
    C = "C"  # Cardiovascular system
    D = "D"  # Dermatologicals
    G = "G"  # Genito-urinary system and sex hormones
    H = "H"  # Systemic hormonal preparations
    J = "J"  # Antiinfectives for systemic use
    L = "L"  # Antineoplastic and immunomodulating agents
    M = "M"  # Musculo-skeletal system
    N = "N"  # Nervous system
    P = "P"  # Antiparasitic products
    R = "R"  # Respiratory system
    S = "S"  # Sensory organs
    V = "V"  # Various


class MeSHTerm(StrEnum):
    """Representative MeSH (Medical Subject Headings) top-level descriptors."""

    NEOPLASMS = "neoplasms"
    NERVOUS_SYSTEM_DISEASES = "nervous_system_diseases"
    CARDIOVASCULAR_DISEASES = "cardiovascular_diseases"
    IMMUNE_SYSTEM_DISEASES = "immune_system_diseases"
    DIGESTIVE_SYSTEM_DISEASES = "digestive_system_diseases"
    ENDOCRINE_SYSTEM_DISEASES = "endocrine_system_diseases"
    RESPIRATORY_TRACT_DISEASES = "respiratory_tract_diseases"
    MUSCULOSKELETAL_DISEASES = "musculoskeletal_diseases"
    HEMATOLOGIC_DISEASES = "hematologic_diseases"
    SKIN_DISEASES = "skin_diseases"
    UROLOGIC_DISEASES = "urologic_diseases"
    INFECTIOUS_DISEASES = "infectious_diseases"
    METABOLIC_DISEASES = "metabolic_diseases"
    GENETIC_DISEASES = "genetic_diseases"
    RARE_DISEASES = "rare_diseases"


class TargetClassification(StrEnum):
    """Functional classification of a molecular target."""

    GPCR = "gpcr"
    KINASE = "kinase"
    NUCLEAR_RECEPTOR = "nuclear_receptor"
    ION_CHANNEL = "ion_channel"
    PROTEASE = "protease"
    PHOSPHATASE = "phosphatase"
    EPIGENETIC_REGULATOR = "epigenetic_regulator"
    TRANSCRIPTION_FACTOR = "transcription_factor"
    UBIQUITIN_LIGASE = "ubiquitin_ligase"
    TRANSPORTER = "transporter"
    STRUCTURAL_PROTEIN = "structural_protein"
    CYTOKINE = "cytokine"
    GROWTH_FACTOR = "growth_factor"
    CHECKPOINT_PROTEIN = "checkpoint_protein"
    ENZYME_OTHER = "enzyme_other"
    NON_CODING_RNA = "non_coding_rna"
    UNKNOWN = "unknown"
