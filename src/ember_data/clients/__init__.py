"""API clients for external biomedical data sources."""

from ember_data.clients.clinicaltrials import ClinicalTrialsClient
from ember_data.clients.pubmed import PubMedClient
from ember_data.clients.uniprot import UniProtClient

__all__ = ["ClinicalTrialsClient", "PubMedClient", "UniProtClient"]
