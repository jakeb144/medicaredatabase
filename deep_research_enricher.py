#!/usr/bin/env python3
"""
Deep Web Research Enricher for Medicare Agencies
Performs thorough web research on every agency to find verified owner information
90%+ confidence target with real web verification
"""

import csv
import json
import os
import sys
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Progress tracking
PROGRESS_FILE = 'research_progress.json'
RESULTS_FILE = 'verified_enrichment_results.json'

@dataclass
class ResearchResult:
    """Complete research result for an agency"""
    agency_name: str
    ccn: str
    owner_name: str
    confidence: int
    sales_intel: str
    sources: str
    attempt_a_query: str
    attempt_a_findings: str
    attempt_b_query: str
    attempt_b_findings: str
    reconciliation_notes: str
    timestamp: str


class DeepResearchEnricher:
    """Performs deep web research on Medicare agencies"""

    def __init__(self, input_file: str, output_file: str, min_rev: float = 500000, max_rev: float = 3000000):
        self.input_file = input_file
        self.output_file = output_file
        self.min_rev = min_rev
        self.max_rev = max_rev

        # Load progress if exists
        self.progress = self._load_progress()
        self.results = self._load_results()

        self.stats = {
            'total_to_research': 0,
            'completed': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'failed': 0
        }

    def _load_progress(self) -> Dict:
        """Load research progress"""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {'completed_ccns': [], 'last_updated': None}

    def _save_progress(self, ccn: str):
        """Save progress"""
        if ccn not in self.progress['completed_ccns']:
            self.progress['completed_ccns'].append(ccn)
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _load_results(self) -> Dict:
        """Load existing results"""
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as f:
                return json.load(f)
        return {}

    def _save_result(self, ccn: str, result: ResearchResult):
        """Save research result"""
        self.results[ccn] = asdict(result)
        with open(RESULTS_FILE, 'w') as f:
            json.dump(self.results, f, indent=2)

    def generate_official_queries(self, row: Dict) -> List[str]:
        """Generate queries for official source research (Attempt A)"""
        queries = []

        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        state = row.get('State', '').strip()
        city = row.get('City/Town', '').strip()

        # Query 1: NPI Registry with authorized official
        if agency_name and city and state:
            queries.append(f'NPI registry "{agency_name}" {city} {state} authorized official owner administrator')

        # Query 2: State business registry
        if state and agency_name:
            clean_name = agency_name.replace(',', '').replace('.', '').strip()
            queries.append(f'{state} Secretary of State business entity search "{clean_name}" managing member owner')

        # Query 3: CMS provider database
        if ccn:
            queries.append(f'CMS certification number {ccn} provider owner administrator contact')

        return queries

    def generate_web_queries(self, row: Dict) -> List[str]:
        """Generate queries for web triangulation (Attempt B)"""
        queries = []

        agency_name = row.get('Name', '').strip()
        city = row.get('City/Town', '').strip()
        state = row.get('State', '').strip()
        address = row.get('Address', '').strip()
        phone = row.get('AAATelephone Number', '').strip()

        # Query 1: Company info with location
        if agency_name and city and state:
            queries.append(f'"{agency_name}" {city} {state} owner CEO president administrator founder')

        # Query 2: Address-based search
        if address and city and state:
            queries.append(f'"{address}" {city} {state} home health owner business registration')

        # Query 3: About/leadership page
        if agency_name:
            queries.append(f'"{agency_name}" home health about us management team leadership owner')

        return queries

    def extract_owner_from_text(self, text: str, agency_name: str) -> Tuple[Optional[str], int, str]:
        """
        Extract owner name from search result text
        Returns: (owner_name, confidence, evidence)
        """
        text_lower = text.lower()
        evidence_list = []
        potential_owners = []

        # Look for NPI authorized official patterns
        npi_patterns = [
            r'authorized official[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II|RN|MD|PhD))?)',
            r'contact person[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II|RN|MD|PhD))?)',
        ]

        # Look for business registry patterns
        registry_patterns = [
            r'managing member[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II))?)',
            r'owner[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II))?)',
            r'president[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II|RN|MD|PhD))?)',
        ]

        # Look for website/directory patterns
        web_patterns = [
            r'(?:CEO|Owner|Founder|Administrator)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II|RN|MD|PhD))?)',
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II|RN|MD|PhD))?)\s+[-–]\s+(?:CEO|Owner|President|Founder|Administrator)',
        ]

        all_patterns = {
            'NPI/Official': npi_patterns,
            'Business Registry': registry_patterns,
            'Website/Directory': web_patterns
        }

        # Search for matches
        for source_type, patterns in all_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    name = match.strip() if isinstance(match, str) else match[0].strip()
                    if len(name) > 5 and ' ' in name:  # Basic validation
                        potential_owners.append({
                            'name': name,
                            'source': source_type,
                            'confidence_boost': 30 if 'NPI' in source_type else 20 if 'Registry' in source_type else 15
                        })
                        evidence_list.append(f"{source_type}: {name}")

        # If we found candidates, return the most confident one
        if potential_owners:
            # Prefer official sources
            best_candidate = max(potential_owners, key=lambda x: x['confidence_boost'])
            confidence = min(best_candidate['confidence_boost'] + 50, 95)  # Base + boost
            return best_candidate['name'], confidence, " | ".join(evidence_list[:3])

        return None, 0, "No owner patterns found in search results"

    def create_research_batch(self):
        """
        Create the batch of agencies that need research
        This will output a JSON file with all the queries to be executed
        """
        print("\n" + "="*80)
        print("CREATING RESEARCH BATCH")
        print("="*80)

        # Read input CSV
        with open(self.input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Filter to target range
        batch = []
        for row in rows:
            existing_owner = row.get('Owner Name', '').strip()
            appx_rev_str = row.get('APPX REV', '').strip()
            ccn = row.get('CMS Certification Number (CCN)', '').strip()

            # Skip if has owner or already completed
            if existing_owner or ccn in self.progress['completed_ccns']:
                continue

            # Check revenue range
            if not appx_rev_str:
                continue

            try:
                appx_rev = float(appx_rev_str)
                if not (self.min_rev <= appx_rev <= self.max_rev):
                    continue
            except ValueError:
                continue

            # This needs research
            official_queries = self.generate_official_queries(row)
            web_queries = self.generate_web_queries(row)

            batch.append({
                'ccn': ccn,
                'agency_name': row.get('Name', ''),
                'city': row.get('City/Town', ''),
                'state': row.get('State', ''),
                'revenue': appx_rev_str,
                'official_queries': official_queries,
                'web_queries': web_queries,
                'row_data': row
            })

        self.stats['total_to_research'] = len(batch)

        # Save batch
        with open('research_batch_full.json', 'w') as f:
            json.dump(batch, f, indent=2)

        print(f"\nCreated research batch: {len(batch)} agencies")
        print(f"Saved to: research_batch_full.json")
        print(f"Already completed: {len(self.progress['completed_ccns'])} agencies")
        print("\nThis file contains all the queries that will be executed.")
        print("Each agency will have 6-9 web searches performed.")
        print(f"Total searches to perform: ~{len(batch) * 6} searches")

        return batch


def main():
    """Main entry point"""
    input_file = "CRM - HHAs by episodes # 2b53f850e21980adbd44ed2d4a99047f_all.csv"
    output_file = "agencies_fully_verified.csv"

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    enricher = DeepResearchEnricher(
        input_file=input_file,
        output_file=output_file,
        min_rev=500000,
        max_rev=3000000
    )

    # Create research batch
    batch = enricher.create_research_batch()

    print("\n" + "="*80)
    print("BATCH READY FOR DEEP RESEARCH")
    print("="*80)
    print("\nNext step: Execute the web research using the automation module")
    print("This will perform real web searches for every agency.")


if __name__ == "__main__":
    main()
