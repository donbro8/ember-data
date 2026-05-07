"""PubMedClient — searches PubMed via NCBI E-utilities for article records."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from ember_data.models.article import Article
from ember_data.models.provenance import SourceProvenance

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_RATE_ANON = 3   # requests/sec without API key
_RATE_KEY = 10   # requests/sec with API key

_MONTH_MAP: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class PubMedClient:
    """Client for NCBI PubMed E-utilities.

    Rate limits
    -----------
    - Without API key: 3 requests/sec (NCBI policy)
    - With API key: 10 requests/sec (NCBI policy for registered users)

    Retry
    -----
    - 3 attempts max, exponential backoff: 1s, 2s, 4s.

    Parameters
    ----------
    api_key:
        Optional NCBI API key. Raises rate limit from 3 to 10 req/sec.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        rate_limit = _RATE_KEY if api_key else _RATE_ANON
        self._min_interval: float = 1.0 / rate_limit
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to stay within the configured rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _build_url(self, endpoint: str, params: dict[str, str]) -> str:
        """Build a full E-utilities URL, injecting api_key when present."""
        all_params: dict[str, str] = dict(params)
        if self._api_key:
            all_params["api_key"] = self._api_key
        query = urllib.parse.urlencode(all_params)
        return f"{_EUTILS_BASE}/{endpoint}?{query}"

    def _get(self, url: str) -> tuple[str, dict[str, str]]:
        """Perform a throttled GET and return (body, headers) tuple."""
        self._throttle()
        req = urllib.request.Request(url, headers={"Accept": "application/json, text/xml"})
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers

    def _retry_get(self, url: str, max_attempts: int = 3) -> tuple[str, dict[str, str]]:
        """Call _get with exponential backoff retry on transient errors.

        Retries on URLError or HTTPError with status >= 429 or >= 500.
        Raises the final exception if all attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._get(url)
            except urllib.error.HTTPError as exc:
                if exc.code >= 429 or exc.code >= 500:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                continue
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # E-utilities wrappers
    # ------------------------------------------------------------------

    def _esearch(self, query: str, retmax: int = 20) -> list[str]:
        """Search PubMed and return a list of PMIDs."""
        url = self._build_url("esearch.fcgi", {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(retmax),
        })
        try:
            body, _ = self._retry_get(url)
            data = json.loads(body)
            return data.get("esearchresult", {}).get("idlist", [])
        except (urllib.error.URLError, ValueError, KeyError):
            return []

    def _efetch(self, pmids: list[str]) -> str:
        """Fetch XML records for a list of PMIDs."""
        url = self._build_url("efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        })
        body, _ = self._retry_get(url)
        return body

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_pub_date(self, pub_date_elem: ET.Element | None) -> date | None:
        """Parse a PubDate XML element into a date object."""
        if pub_date_elem is None:
            return None

        year_elem = pub_date_elem.find("Year")
        if year_elem is None or not year_elem.text:
            # Try MedlineDate fallback
            medline_elem = pub_date_elem.find("MedlineDate")
            if medline_elem is not None and medline_elem.text:
                # e.g. "2023 Jan-Feb" — grab first 4-digit year
                parts = medline_elem.text.strip().split()
                if parts and parts[0].isdigit() and len(parts[0]) == 4:
                    return date(int(parts[0]), 1, 1)
            return None

        year = int(year_elem.text.strip())

        month_elem = pub_date_elem.find("Month")
        month = 1
        if month_elem is not None and month_elem.text:
            month_str = month_elem.text.strip().lower()
            if month_str.isdigit():
                month = int(month_str)
            else:
                month = _MONTH_MAP.get(month_str[:3], 1)

        day_elem = pub_date_elem.find("Day")
        day = 1
        if day_elem is not None and day_elem.text:
            try:
                day = int(day_elem.text.strip())
            except ValueError:
                day = 1

        try:
            return date(year, month, day)
        except ValueError:
            return date(year, 1, 1)

    def _parse_article(self, article_elem: ET.Element) -> Article | None:
        """Parse a PubmedArticle XML element into an Article domain object."""
        medline = article_elem.find("MedlineCitation")
        if medline is None:
            return None

        pmid_elem = medline.find("PMID")
        pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else None

        article_node = medline.find("Article")
        if article_node is None:
            return None

        title_elem = article_node.find("ArticleTitle")
        title = title_elem.text or "" if title_elem is not None else ""
        # Strip any trailing whitespace/newlines that can appear with inline XML
        title = (title or "").strip()

        # Authors
        authors: list[str] = []
        author_list = article_node.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None and last.text:
                    name = last.text.strip()
                    if fore is not None and fore.text:
                        name = f"{name} {fore.text.strip()}"
                    authors.append(name)
                else:
                    # CollectiveName fallback
                    coll = author.find("CollectiveName")
                    if coll is not None and coll.text:
                        authors.append(coll.text.strip())

        # Journal
        journal_node = article_node.find("Journal")
        journal = ""
        pub_date: date | None = None
        if journal_node is not None:
            journal_title = journal_node.find("Title")
            journal = journal_title.text.strip() if journal_title is not None and journal_title.text else ""
            issue = journal_node.find("JournalIssue")
            if issue is not None:
                pub_date = self._parse_pub_date(issue.find("PubDate"))

        if pub_date is None:
            return None

        # Abstract
        abstract_node = article_node.find("Abstract")
        abstract = ""
        if abstract_node is not None:
            parts: list[str] = []
            for text_elem in abstract_node.findall("AbstractText"):
                text = text_elem.text or ""
                if text.strip():
                    parts.append(text.strip())
            abstract = " ".join(parts)

        # MeSH terms
        mesh_terms: list[str] = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for heading in mesh_list.findall("MeshHeading"):
                desc = heading.find("DescriptorName")
                if desc is not None and desc.text:
                    mesh_terms.append(desc.text.strip())

        # DOI from PubmedData
        doi: str | None = None
        pubmed_data = article_elem.find("PubmedData")
        if pubmed_data is not None:
            id_list = pubmed_data.find("ArticleIdList")
            if id_list is not None:
                for article_id in id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "doi" and article_id.text:
                        doi = article_id.text.strip()
                        break

        return Article(
            pmid=pmid,
            title=title,
            authors=authors,
            journal=journal,
            pub_date=pub_date,
            abstract=abstract,
            mesh_terms=mesh_terms,
            cited_by_count=0,
            doi=doi,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        mesh_term: str | None = None,
        target: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        max_results: int = 20,
    ) -> list[tuple[Article, SourceProvenance]]:
        """Search PubMed for articles matching the given criteria.

        Parameters
        ----------
        mesh_term:
            MeSH term to search (uses ``[MeSH Terms]`` field tag).
        target:
            Gene/protein name to search in title/abstract.
        from_date:
            Start of publication date range.
        to_date:
            End of publication date range.
        max_results:
            Maximum number of results to return.

        Returns
        -------
        list of (Article, SourceProvenance) tuples.
        """
        if not mesh_term and not target:
            return []

        query_parts: list[str] = []
        matched_fields: list[str] = []

        if mesh_term:
            query_parts.append(f"{mesh_term}[MeSH Terms]")
            matched_fields.append("mesh_term")
        if target:
            query_parts.append(f"{target}[Title/Abstract]")
            matched_fields.append("target")

        query = " AND ".join(query_parts)

        if from_date or to_date:
            start = from_date.strftime("%Y/%m/%d") if from_date else "1900/01/01"
            end = to_date.strftime("%Y/%m/%d") if to_date else "3000/12/31"
            query += f" AND {start}:{end}[PDAT]"

        pmids = self._esearch(query, retmax=max_results)
        if not pmids:
            return []

        try:
            xml_body = self._efetch(pmids)
        except (urllib.error.URLError, OSError):
            return []

        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError:
            return []

        results: list[tuple[Article, SourceProvenance]] = []
        for article_elem in root.findall("PubmedArticle"):
            article = self._parse_article(article_elem)
            if article is None:
                continue
            pmid_val = article.pmid or ""
            provenance = SourceProvenance(
                source_name="PubMed",
                source_id=pmid_val,
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid_val}/",
                retrieved_at=datetime.now(UTC),
                matched_fields=matched_fields,
            )
            results.append((article, provenance))

        return results
