"""Tests for ClinicalTrialsClient, PubMedClient, UniProtClient."""

from __future__ import annotations

import json
import urllib.error
from datetime import date, datetime
from unittest.mock import patch

import pytest

from ember_data.clients.clinicaltrials import ClinicalTrialsClient
from ember_data.clients.pubmed import PubMedClient
from ember_data.clients.uniprot import UniProtClient
from ember_data.models.article import Article
from ember_data.models.provenance import SourceProvenance
from ember_data.models.target import Target, TargetType
from ember_data.models.trial import Trial, TrialPhase

# ---------------------------------------------------------------------------
# Fixtures — ClinicalTrials.gov
# ---------------------------------------------------------------------------

_CT_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT01234567",
            "officialTitle": "A Phase II Study of Drug X in Breast Cancer",
            "briefTitle": "Drug X in Breast Cancer",
        },
        "designModule": {
            "phases": ["PHASE2"],
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2022-03"},
        },
        "conditionsModule": {
            "conditions": ["Breast Cancer"],
        },
        "armsInterventionsModule": {
            "interventions": [{"name": "Drug X"}, {"name": "Placebo"}],
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Acme Pharma"},
        },
        "outcomesModule": {
            "primaryOutcomes": [{"measure": "Overall Response Rate"}],
        },
    }
}

_CT_RESPONSE = {"studies": [_CT_STUDY]}

# Study with PHASE1 and date as YYYY-MM-DD
_CT_STUDY_P1 = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT09876543",
            "officialTitle": "Phase I Dose Escalation of Drug Y",
            "briefTitle": "Drug Y Phase I",
        },
        "designModule": {"phases": ["PHASE1"]},
        "statusModule": {
            "overallStatus": "COMPLETED",
            "startDateStruct": {"date": "2019-06-15"},
        },
        "conditionsModule": {"conditions": ["Lung Cancer"]},
        "armsInterventionsModule": {"interventions": [{"name": "Drug Y"}]},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "BioTech Inc"}},
        "outcomesModule": {"primaryOutcomes": [{"measure": "DLT rate"}]},
    }
}

# Study with unmappable phase — should be skipped
_CT_STUDY_INVALID_PHASE = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT00000001",
            "officialTitle": "Early Phase 1 Study",
            "briefTitle": "Early Phase 1",
        },
        "designModule": {"phases": ["EARLY_PHASE1"]},
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2020-01"},
        },
        "conditionsModule": {"conditions": ["Cancer"]},
        "armsInterventionsModule": {"interventions": []},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
        "outcomesModule": {"primaryOutcomes": []},
    }
}


# ---------------------------------------------------------------------------
# Fixtures — PubMed
# ---------------------------------------------------------------------------

_ESEARCH_RESPONSE = json.dumps({
    "esearchresult": {
        "count": "2",
        "idlist": ["12345678", "87654321"],
    }
})

_EFETCH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">12345678</PMID>
      <Article PubModel="Print">
        <Journal>
          <Title>Nature Medicine</Title>
          <JournalIssue CitedMedium="Print">
            <PubDate>
              <Year>2023</Year>
              <Month>Jun</Month>
              <Day>1</Day>
            </PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>EGFR inhibition in lung cancer</ArticleTitle>
        <Abstract>
          <AbstractText>This study examines EGFR inhibition effects.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
          <Author ValidYN="Y">
            <LastName>Doe</LastName>
            <ForeName>Jane</ForeName>
          </Author>
        </AuthorList>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D008175" MajorTopicYN="Y">Lung Neoplasms</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1038/nm.1234</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

_EFETCH_XML_NO_ABSTRACT = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">99999999</PMID>
      <Article PubModel="Print">
        <Journal>
          <Title>Lancet</Title>
          <JournalIssue CitedMedium="Print">
            <PubDate>
              <Year>2021</Year>
            </PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>A brief report</ArticleTitle>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Brown</LastName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">99999999</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


# ---------------------------------------------------------------------------
# Fixtures — UniProt
# ---------------------------------------------------------------------------

_UNIPROT_ENTRY = {
    "primaryAccession": "P04626",
    "genes": [
        {
            "geneName": {"value": "ERBB2"},
            "synonyms": [{"value": "HER2"}, {"value": "NEU"}],
        }
    ],
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Receptor tyrosine-protein kinase erbB-2"}
        }
    },
    "organism": {
        "scientificName": "Homo sapiens",
        "taxonId": 9606,
    },
}

_UNIPROT_SEARCH_RESPONSE = {
    "results": [_UNIPROT_ENTRY],
}

_UNIPROT_ENTRY_NO_GENE = {
    "primaryAccession": "A0A000",
    "genes": [],
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Some unnamed protein"}
        }
    },
    "organism": {
        "scientificName": "Homo sapiens",
        "taxonId": 9606,
    },
}


# ===========================================================================
# ClinicalTrialsClient tests
# ===========================================================================


class TestClinicalTrialsRateLimit:
    def test_rate_is_3_per_sec(self) -> None:
        client = ClinicalTrialsClient()
        assert client._min_interval == pytest.approx(1.0 / 3, rel=1e-3)


class TestClinicalTrialsSearch:
    def test_search_returns_trial_and_provenance(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(_CT_RESPONSE), {})
        ):
            results = client.search(condition="breast cancer")

        assert len(results) == 1
        trial, prov = results[0]
        assert isinstance(trial, Trial)
        assert isinstance(prov, SourceProvenance)

    def test_trial_fields_mapped_correctly(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(_CT_RESPONSE), {})
        ):
            results = client.search(condition="breast cancer")

        trial, _ = results[0]
        assert trial.nct_id == "NCT01234567"
        assert trial.title == "A Phase II Study of Drug X in Breast Cancer"
        assert trial.phase == TrialPhase.II
        assert trial.status == "RECRUITING"
        assert "Breast Cancer" in trial.conditions
        assert "Drug X" in trial.interventions
        assert trial.sponsor == "Acme Pharma"
        assert trial.start_date == date(2022, 3, 1)
        assert "Overall Response Rate" in trial.primary_endpoints
        assert trial.results_summary is None

    def test_provenance_fields(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(_CT_RESPONSE), {})
        ):
            results = client.search(condition="breast cancer")

        _, prov = results[0]
        assert prov.source_name == "ClinicalTrials.gov"
        assert prov.source_id == "NCT01234567"
        assert prov.source_url == "https://clinicaltrials.gov/study/NCT01234567"
        assert isinstance(prov.retrieved_at, datetime)
        assert "condition" in prov.matched_fields

    def test_intervention_adds_to_matched_fields(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(_CT_RESPONSE), {})
        ):
            results = client.search(condition="breast cancer", intervention="Drug X")

        _, prov = results[0]
        assert "intervention" in prov.matched_fields
        assert "condition" in prov.matched_fields

    def test_phase1_mapped_correctly(self) -> None:
        client = ClinicalTrialsClient()
        response = {"studies": [_CT_STUDY_P1]}
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(response), {})
        ):
            results = client.search(condition="lung cancer")

        assert len(results) == 1
        trial, _ = results[0]
        assert trial.phase == TrialPhase.I
        assert trial.start_date == date(2019, 6, 15)

    def test_invalid_phase_skipped(self) -> None:
        client = ClinicalTrialsClient()
        response = {"studies": [_CT_STUDY_INVALID_PHASE]}
        with patch.object(
            client, "_retry_get", return_value=(json.dumps(response), {})
        ):
            results = client.search(condition="cancer")

        assert results == []

    def test_empty_studies_returns_empty(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", return_value=(json.dumps({"studies": []}), {})
        ):
            results = client.search(condition="cancer")

        assert results == []

    def test_network_error_returns_empty(self) -> None:
        client = ClinicalTrialsClient()
        with patch.object(
            client, "_retry_get", side_effect=urllib.error.URLError("timeout")
        ):
            results = client.search(condition="cancer")

        assert results == []

    def test_date_filter_included_in_url(self) -> None:
        """Verify from_date and to_date appear in the URL passed to _retry_get."""
        client = ClinicalTrialsClient()
        captured_urls: list[str] = []

        def capture_url(url: str, max_attempts: int = 3) -> tuple[str, dict]:
            captured_urls.append(url)
            return json.dumps({"studies": []}), {}

        with patch.object(client, "_retry_get", side_effect=capture_url):
            client.search(
                condition="cancer",
                from_date=date(2020, 1, 1),
                to_date=date(2023, 12, 31),
            )

        assert captured_urls, "No URL was captured"
        url = captured_urls[0]
        assert "2023-12-31" in url

    def test_max_results_in_url(self) -> None:
        client = ClinicalTrialsClient()
        captured_urls: list[str] = []

        def capture_url(url: str, max_attempts: int = 3) -> tuple[str, dict]:
            captured_urls.append(url)
            return json.dumps({"studies": []}), {}

        with patch.object(client, "_retry_get", side_effect=capture_url):
            client.search(condition="cancer", max_results=5)

        assert "pageSize=5" in captured_urls[0]


# ===========================================================================
# PubMedClient tests
# ===========================================================================


class TestPubMedRateLimit:
    def test_default_rate_is_3_per_sec(self) -> None:
        client = PubMedClient()
        assert client._min_interval == pytest.approx(1.0 / 3, rel=1e-3)

    def test_api_key_rate_is_10_per_sec(self) -> None:
        client = PubMedClient(api_key="test-key")
        assert client._min_interval == pytest.approx(1.0 / 10, rel=1e-3)


class TestPubMedSearch:
    def test_search_returns_article_and_provenance(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["12345678"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML):
            results = client.search(mesh_term="Lung Neoplasms")

        assert len(results) == 1
        article, prov = results[0]
        assert isinstance(article, Article)
        assert isinstance(prov, SourceProvenance)

    def test_article_fields_mapped_correctly(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["12345678"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML):
            results = client.search(mesh_term="Lung Neoplasms")

        article, _ = results[0]
        assert article.pmid == "12345678"
        assert article.title == "EGFR inhibition in lung cancer"
        assert article.journal == "Nature Medicine"
        assert article.pub_date == date(2023, 6, 1)
        assert "Smith John" in article.authors
        assert "Doe Jane" in article.authors
        assert "This study examines EGFR inhibition effects." in article.abstract
        assert "Lung Neoplasms" in article.mesh_terms
        assert article.doi == "10.1038/nm.1234"
        assert article.cited_by_count == 0

    def test_provenance_fields(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["12345678"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML):
            results = client.search(mesh_term="Lung Neoplasms")

        _, prov = results[0]
        assert prov.source_name == "PubMed"
        assert prov.source_id == "12345678"
        assert prov.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert isinstance(prov.retrieved_at, datetime)
        assert "mesh_term" in prov.matched_fields

    def test_target_search_matched_fields(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["12345678"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML):
            results = client.search(target="EGFR")

        _, prov = results[0]
        assert "target" in prov.matched_fields

    def test_both_mesh_and_target_in_matched_fields(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["12345678"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML):
            results = client.search(mesh_term="Lung Neoplasms", target="EGFR")

        _, prov = results[0]
        assert "mesh_term" in prov.matched_fields
        assert "target" in prov.matched_fields

    def test_no_search_term_returns_empty(self) -> None:
        client = PubMedClient()
        results = client.search()
        assert results == []

    def test_empty_pmids_returns_empty(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=[]):
            results = client.search(mesh_term="Rare Condition")

        assert results == []

    def test_date_filter_in_query(self) -> None:
        """Verify date range is included in the esearch query."""
        client = PubMedClient()
        captured_queries: list[str] = []

        def capture_query(query: str, retmax: int = 20) -> list[str]:
            captured_queries.append(query)
            return []

        with patch.object(client, "_esearch", side_effect=capture_query):
            client.search(
                mesh_term="Cancer",
                from_date=date(2020, 1, 1),
                to_date=date(2023, 12, 31),
            )

        assert captured_queries
        query = captured_queries[0]
        assert "2020/01/01" in query
        assert "2023/12/31" in query
        assert "[PDAT]" in query

    def test_mesh_term_uses_mesh_field_tag(self) -> None:
        client = PubMedClient()
        captured_queries: list[str] = []

        def capture_query(query: str, retmax: int = 20) -> list[str]:
            captured_queries.append(query)
            return []

        with patch.object(client, "_esearch", side_effect=capture_query):
            client.search(mesh_term="Breast Cancer")

        assert "[MeSH Terms]" in captured_queries[0]

    def test_target_uses_title_abstract_field_tag(self) -> None:
        client = PubMedClient()
        captured_queries: list[str] = []

        def capture_query(query: str, retmax: int = 20) -> list[str]:
            captured_queries.append(query)
            return []

        with patch.object(client, "_esearch", side_effect=capture_query):
            client.search(target="BRCA1")

        assert "[Title/Abstract]" in captured_queries[0]

    def test_article_with_no_abstract_still_parses(self) -> None:
        client = PubMedClient()
        with patch.object(client, "_esearch", return_value=["99999999"]), \
             patch.object(client, "_efetch", return_value=_EFETCH_XML_NO_ABSTRACT):
            results = client.search(target="report")

        assert len(results) == 1
        article, _ = results[0]
        assert article.pmid == "99999999"
        assert article.abstract == ""

    def test_api_key_included_in_esearch_url(self) -> None:
        client = PubMedClient(api_key="my-api-key")
        url = client._build_url("esearch.fcgi", {"db": "pubmed", "term": "test"})
        assert "api_key=my-api-key" in url

    def test_no_api_key_omitted_from_url(self) -> None:
        client = PubMedClient()
        url = client._build_url("esearch.fcgi", {"db": "pubmed", "term": "test"})
        assert "api_key" not in url


# ===========================================================================
# UniProtClient tests
# ===========================================================================


class TestUniProtRateLimit:
    def test_rate_is_5_per_sec(self) -> None:
        client = UniProtClient()
        assert client._min_interval == pytest.approx(1.0 / 5, rel=1e-3)


class TestUniProtSearchTargets:
    def test_search_returns_target_and_provenance(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_SEARCH_RESPONSE), {}),
        ):
            results = client.search_targets("ERBB2")

        assert len(results) == 1
        target, prov = results[0]
        assert isinstance(target, Target)
        assert isinstance(prov, SourceProvenance)

    def test_target_fields_mapped_correctly(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_SEARCH_RESPONSE), {}),
        ):
            results = client.search_targets("ERBB2")

        target, _ = results[0]
        assert target.id == "P04626"
        assert target.name == "ERBB2"
        assert target.type == TargetType.PROTEIN
        assert target.organism == "Homo sapiens"
        assert "HER2" in target.aliases
        assert "NEU" in target.aliases
        assert target.uniprot_id == "P04626"
        assert target.gene_id is None

    def test_protein_name_in_aliases_when_different_from_name(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_SEARCH_RESPONSE), {}),
        ):
            results = client.search_targets("ERBB2")

        target, _ = results[0]
        assert "Receptor tyrosine-protein kinase erbB-2" in target.aliases

    def test_provenance_fields(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_SEARCH_RESPONSE), {}),
        ):
            results = client.search_targets("ERBB2")

        _, prov = results[0]
        assert prov.source_name == "UniProt"
        assert prov.source_id == "P04626"
        assert prov.source_url == "https://www.uniprot.org/uniprot/P04626"
        assert isinstance(prov.retrieved_at, datetime)
        assert "gene_name" in prov.matched_fields

    def test_empty_results_returns_empty(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps({"results": []}), {}),
        ):
            results = client.search_targets("XYZ_UNKNOWN")

        assert results == []

    def test_network_error_returns_empty(self) -> None:
        client = UniProtClient()
        with patch.object(
            client, "_retry_get", side_effect=urllib.error.URLError("timeout")
        ):
            results = client.search_targets("EGFR")

        assert results == []

    def test_entry_without_gene_uses_protein_name(self) -> None:
        client = UniProtClient()
        response = {"results": [_UNIPROT_ENTRY_NO_GENE]}
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(response), {}),
        ):
            results = client.search_targets("protein")

        assert len(results) == 1
        target, _ = results[0]
        assert target.name == "Some unnamed protein"

    def test_organism_id_included_in_query_url(self) -> None:
        client = UniProtClient()
        captured_urls: list[str] = []

        def capture_url(url: str, max_attempts: int = 3) -> tuple[str, dict]:
            captured_urls.append(url)
            return json.dumps({"results": []}), {}

        with patch.object(client, "_retry_get", side_effect=capture_url):
            client.search_targets("EGFR", organism_id=10090)  # mouse

        assert captured_urls
        assert "10090" in captured_urls[0]


class TestUniProtGetTarget:
    def test_get_target_returns_target_and_provenance(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_ENTRY), {}),
        ):
            result = client.get_target("P04626")

        assert result is not None
        target, prov = result
        assert isinstance(target, Target)
        assert isinstance(prov, SourceProvenance)

    def test_get_target_fields(self) -> None:
        client = UniProtClient()
        with patch.object(
            client,
            "_retry_get",
            return_value=(json.dumps(_UNIPROT_ENTRY), {}),
        ):
            result = client.get_target("P04626")

        assert result is not None
        target, _ = result
        assert target.id == "P04626"
        assert target.name == "ERBB2"
        assert target.uniprot_id == "P04626"

    def test_get_target_not_found_returns_none(self) -> None:
        client = UniProtClient()
        err = urllib.error.HTTPError(
            url="https://rest.uniprot.org/uniprotkb/INVALID",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,  # type: ignore[arg-type]
        )
        with patch.object(client, "_retry_get", side_effect=err):
            result = client.get_target("INVALID")

        assert result is None

    def test_get_target_network_error_returns_none(self) -> None:
        client = UniProtClient()
        with patch.object(
            client, "_retry_get", side_effect=urllib.error.URLError("timeout")
        ):
            result = client.get_target("P04626")

        assert result is None


# ===========================================================================
# Retry logic tests
# ===========================================================================


class TestRetryLogic:
    def test_clinicaltrials_retries_on_429(self) -> None:
        client = ClinicalTrialsClient()
        call_count = 0

        def flaky_get(url: str) -> tuple[str, dict]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.HTTPError(
                    url=url, code=429, msg="Too Many Requests",
                    hdrs=None, fp=None,  # type: ignore[arg-type]
                )
            return json.dumps({"studies": []}), {}

        with patch.object(client, "_get", side_effect=flaky_get), \
             patch("ember_data.clients.clinicaltrials.time.sleep"):
            result = client._retry_get("https://example.com")

        assert call_count == 3
        assert result[0] == json.dumps({"studies": []})

    def test_clinicaltrials_raises_after_max_attempts(self) -> None:
        client = ClinicalTrialsClient()

        def always_fail(url: str) -> tuple[str, dict]:
            raise urllib.error.URLError("timeout")

        with patch.object(client, "_get", side_effect=always_fail), \
             patch("ember_data.clients.clinicaltrials.time.sleep"):
            with pytest.raises(urllib.error.URLError):
                client._retry_get("https://example.com", max_attempts=3)

    def test_pubmed_retries_on_500(self) -> None:
        client = PubMedClient()
        call_count = 0

        def flaky_get(url: str) -> tuple[str, dict]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(
                    url=url, code=500, msg="Internal Server Error",
                    hdrs=None, fp=None,  # type: ignore[arg-type]
                )
            return '{"esearchresult": {"idlist": []}}', {}

        with patch.object(client, "_get", side_effect=flaky_get), \
             patch("ember_data.clients.pubmed.time.sleep"):
            client._retry_get("https://example.com")

        assert call_count == 2

    def test_uniprot_retries_on_urlerror(self) -> None:
        client = UniProtClient()
        call_count = 0

        def flaky_get(url: str) -> tuple[str, dict]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.URLError("connection reset")
            return json.dumps({"results": []}), {}

        with patch.object(client, "_get", side_effect=flaky_get), \
             patch("ember_data.clients.uniprot.time.sleep"):
            client._retry_get("https://example.com")

        assert call_count == 2

    def test_clinicaltrials_does_not_retry_on_404(self) -> None:
        """HTTP 404 should not be retried — it is raised immediately."""
        client = ClinicalTrialsClient()
        call_count = 0

        def not_found(url: str) -> tuple[str, dict]:
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                url=url, code=404, msg="Not Found",
                hdrs=None, fp=None,  # type: ignore[arg-type]
            )

        with patch.object(client, "_get", side_effect=not_found):
            with pytest.raises(urllib.error.HTTPError):
                client._retry_get("https://example.com")

        assert call_count == 1
