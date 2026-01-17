#!/usr/bin/env python3
"""
Research Assistant Module
This module provides templates and structures for web-based owner research
Can be integrated with automated web search or used for manual research
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ResearchQuery:
    """Represents a research query to be executed"""
    query_type: str  # 'official' or 'web'
    query_text: str
    agency_name: str
    ccn: str
    priority: int = 1  # 1 = high, 2 = medium, 3 = low


@dataclass
class ResearchFinding:
    """Represents a finding from research"""
    owner_name: str
    source: str
    confidence: int
    evidence: str
    url: Optional[str] = None


class ResearchAssistant:
    """Assists with web research for agency owners"""

    def __init__(self):
        self.findings_cache = {}

    def generate_official_queries(self, row: Dict) -> List[ResearchQuery]:
        """Generate queries for official source research (Attempt A)"""
        queries = []

        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        state = row.get('State', '').strip()
        city = row.get('City/Town', '').strip()

        # Query 1: CMS/Medicare provider lookup
        if ccn:
            queries.append(ResearchQuery(
                query_type='official',
                query_text=f'CMS certification number {ccn} owner administrator',
                agency_name=agency_name,
                ccn=ccn,
                priority=1
            ))

        # Query 2: State business registry
        if state and agency_name:
            # Clean agency name for business search
            business_name = agency_name.replace(',', '').replace('.', '')
            queries.append(ResearchQuery(
                query_type='official',
                query_text=f'{state} secretary of state business search {business_name}',
                agency_name=agency_name,
                ccn=ccn,
                priority=1
            ))

        # Query 3: NPI registry lookup
        if agency_name and city and state:
            queries.append(ResearchQuery(
                query_type='official',
                query_text=f'NPI registry {agency_name} {city} {state} authorized official',
                agency_name=agency_name,
                ccn=ccn,
                priority=2
            ))

        return queries

    def generate_web_queries(self, row: Dict) -> List[ResearchQuery]:
        """Generate queries for web triangulation research (Attempt B)"""
        queries = []

        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        city = row.get('City/Town', '').strip()
        state = row.get('State', '').strip()
        address = row.get('Address', '').strip()
        phone = row.get('AAATelephone Number', '').strip()

        # Query 1: Agency name + location + owner
        if agency_name and city and state:
            queries.append(ResearchQuery(
                query_type='web',
                query_text=f'"{agency_name}" {city} {state} owner CEO administrator',
                agency_name=agency_name,
                ccn=ccn,
                priority=1
            ))

        # Query 2: Address-based lookup
        if address and city:
            queries.append(ResearchQuery(
                query_type='web',
                query_text=f'"{address}" {city} business owner',
                agency_name=agency_name,
                ccn=ccn,
                priority=2
            ))

        # Query 3: Company website about page
        if agency_name:
            queries.append(ResearchQuery(
                query_type='web',
                query_text=f'"{agency_name}" home health about us management team',
                agency_name=agency_name,
                ccn=ccn,
                priority=2
            ))

        # Query 4: LinkedIn company page
        if agency_name:
            queries.append(ResearchQuery(
                query_type='web',
                query_text=f'linkedin {agency_name} home health CEO owner',
                agency_name=agency_name,
                ccn=ccn,
                priority=3
            ))

        return queries

    def parse_research_results(self, results_text: str, source: str) -> List[ResearchFinding]:
        """
        Parse research results to extract owner information
        This is a template - would need actual NLP/parsing logic
        """
        findings = []

        # Look for common patterns indicating ownership
        patterns = [
            r'Owner:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Managing Member:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Administrator:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'CEO:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'President:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]

        import re
        for pattern in patterns:
            matches = re.findall(pattern, results_text)
            for match in matches:
                findings.append(ResearchFinding(
                    owner_name=match.strip(),
                    source=source,
                    confidence=60,  # Default confidence
                    evidence=f"Found via pattern matching in {source}"
                ))

        return findings

    def create_research_batch_file(self, rows: List[Dict], output_file: str = 'research_batch.json'):
        """
        Create a batch file of research queries that can be processed
        """
        batch = []

        for i, row in enumerate(rows):
            agency_name = row.get('Name', '')
            ccn = row.get('CMS Certification Number (CCN)', '')

            # Generate all queries for this agency
            official_queries = self.generate_official_queries(row)
            web_queries = self.generate_web_queries(row)

            batch_item = {
                'index': i,
                'agency_name': agency_name,
                'ccn': ccn,
                'row_data': row,
                'official_queries': [asdict(q) for q in official_queries],
                'web_queries': [asdict(q) for q in web_queries],
                'status': 'pending'
            }

            batch.append(batch_item)

        # Save to file
        with open(output_file, 'w') as f:
            json.dump(batch, f, indent=2)

        logger.info(f"Created research batch file: {output_file}")
        logger.info(f"Total agencies to research: {len(batch)}")
        logger.info(f"Total queries: {sum(len(item['official_queries']) + len(item['web_queries']) for item in batch)}")

        return output_file

    def load_research_results(self, results_file: str) -> Dict:
        """Load research results from file"""
        with open(results_file, 'r') as f:
            return json.load(f)


def create_manual_research_template(row: Dict) -> str:
    """Create a manual research template for human researchers"""
    template = f"""
====================================
AGENCY RESEARCH TEMPLATE
====================================
Agency: {row.get('Name', '')}
CCN: {row.get('CMS Certification Number (CCN)', '')}
Address: {row.get('Address', '')}, {row.get('City/Town', '')}, {row.get('State', '')} {row.get('ZIP Code', '')}
Phone: {row.get('AAATelephone Number', '')}
APPX REV: ${row.get('APPX REV', '')}

ATTEMPT A - OFFICIAL SOURCES:
[ ] 1. CMS Provider Lookup: https://www.cms.gov/medicare/provider-enrollment-and-certification/
    CCN: {row.get('CMS Certification Number (CCN)', '')}
    Owner/Administrator found: _______________________
    Source URL: _____________________________________

[ ] 2. State Business Registry: {row.get('State', '')} Secretary of State
    Search for: {row.get('Name', '')}
    Managing Member/Owner: __________________________
    Source URL: _____________________________________

[ ] 3. NPI Registry: https://npiregistry.cms.hhs.gov/
    Search: {row.get('Name', '')}
    Authorized Official: ____________________________
    Source URL: _____________________________________

ATTEMPT B - WEB RESEARCH:
[ ] 1. Google Search: "{row.get('Name', '')} {row.get('City/Town', '')} owner"
    Owner found: ____________________________________
    Source URL: _____________________________________

[ ] 2. Company Website:
    Website: ________________________________________
    About/Management page owner: ____________________
    Source URL: _____________________________________

[ ] 3. LinkedIn:
    Company page: ___________________________________
    CEO/Owner listed: _______________________________
    Source URL: _____________________________________

RECONCILIATION:
Attempt A Result: ___________________________________
Attempt B Result: ___________________________________
Do they agree? [ ] Yes [ ] No
Final Owner Name: ___________________________________
Confidence (0-100): _________________________________

SALES INTEL (2-6 bullet points):
• _________________________________________________
• _________________________________________________
• _________________________________________________
• _________________________________________________

SOURCES (list all URLs):
1. _________________________________________________
2. _________________________________________________
3. _________________________________________________
"""
    return template


if __name__ == "__main__":
    # Example usage
    print("Research Assistant Module")
    print("This module provides research query generation and templates.")
    print("Import this module into enrich_owners.py for enhanced research capabilities.")
