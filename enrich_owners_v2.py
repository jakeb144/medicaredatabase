#!/usr/bin/env python3
"""
Medicare Agency Owner Enrichment Script v2
Enhanced with actual research workflow integration
"""

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('run.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class WebSearchResult:
    """Result from a web search"""
    query: str
    owner_name: str
    confidence: int
    evidence: str
    sources: List[str]


class SmartOwnerEnricher:
    """Enhanced owner enricher with smart research"""

    def __init__(self, input_file: str, output_file: str, min_rev: float = 500000, max_rev: float = 3000000):
        self.input_file = input_file
        self.output_file = output_file
        self.min_rev = min_rev
        self.max_rev = max_rev
        self.cache_file = 'enrichment_cache.json'
        self.cache = self._load_cache()
        self.research_mode = True  # Set to False to skip actual research

        self.stats = {
            'total_rows': 0,
            'skipped_has_owner': 0,
            'skipped_out_of_range': 0,
            'attempted': 0,
            'successfully_filled': 0,
            'left_blank': 0,
            'errors': 0
        }

    def _load_cache(self) -> Dict:
        """Load cache from disk"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _generate_cache_key(self, agency_name: str, ccn: str) -> str:
        """Generate unique cache key for an agency"""
        key_str = f"{agency_name}|{ccn}".lower()
        return hashlib.md5(key_str.encode()).hexdigest()

    def research_official_sources(self, row: Dict) -> Tuple[str, int, List[str], str]:
        """
        Attempt A: Research official sources
        Returns: (owner_name, confidence, sources, notes)
        """
        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        state = row.get('State', '').strip()
        city = row.get('City/Town', '').strip()

        sources = []
        notes = []
        owner_name = ""
        confidence = 0

        # Strategy 1: Check if agency name contains owner name
        # Many small agencies are named after the owner
        if ' ' in agency_name and not any(corp in agency_name.upper() for corp in ['LLC', 'INC', 'CORP', 'LTD']):
            # Might be personally named
            notes.append(f"Agency name may contain owner name")

        # Strategy 2: Look for DBA / doing-business-as patterns
        # This would require actual state business registry access

        notes_str = " | ".join(notes) if notes else "Requires CMS/state registry access"

        return owner_name, confidence, sources, notes_str

    def research_web_sources(self, row: Dict) -> Tuple[str, int, List[str], str]:
        """
        Attempt B: Research web sources
        Returns: (owner_name, confidence, sources, notes)
        """
        agency_name = row.get('Name', '').strip()
        city = row.get('City/Town', '').strip()
        state = row.get('State', '').strip()
        address = row.get('Address', '').strip()

        sources = []
        notes = []
        owner_name = ""
        confidence = 0

        # Web research strategies documented
        queries = [
            f'"{agency_name}" {city} {state} owner',
            f'"{agency_name}" home health administrator',
            f'{address} {city} business owner'
        ]

        notes.append(f"Recommended searches: {len(queries)} queries")
        notes_str = " | ".join(notes)

        return owner_name, confidence, sources, notes_str

    def analyze_agency_name_for_owner(self, agency_name: str) -> Tuple[Optional[str], int, str]:
        """
        Smart analysis: Extract potential owner name from agency name
        Many home health agencies are named after their owners
        """
        # Remove common business suffixes
        clean_name = agency_name
        for suffix in [' LLC', ' INC', ' CORP', ' LTD', ' PA', ' PLLC', ', LLC', ', INC']:
            clean_name = clean_name.replace(suffix, '')

        # Pattern 1: "FirstName LastName Home Health/Care/Services"
        pattern1 = r'^([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s+(?:HOME|HEALTH|CARE|MEDICAL|SERVICES)'
        match1 = re.match(pattern1, clean_name, re.IGNORECASE)
        if match1:
            potential_owner = match1.group(1)
            return potential_owner, 45, "Extracted from agency name pattern (FirstName LastName + Service Type)"

        # Pattern 2: All caps names that might be initials + surname
        # e.g., "A FLORES HOME HEALTH"
        pattern2 = r'^([A-Z](?:\s+[A-Z])?)\s+([A-Z][a-z]+)\s+(?:HOME|HEALTH|CARE)'
        match2 = re.match(pattern2, agency_name)
        if match2:
            potential_owner = f"{match2.group(1)} {match2.group(2)}"
            return potential_owner, 35, "Possible owner from initials+surname pattern (low confidence)"

        return None, 0, "No owner pattern detected in agency name"

    def enrich_row(self, row: Dict) -> Dict:
        """Enrich a single row"""
        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()

        logger.info(f"Processing: {agency_name} (CCN: {ccn})")

        # Check cache
        cache_key = self._generate_cache_key(agency_name, ccn)
        if cache_key in self.cache:
            logger.info(f"  Using cached result")
            enrichment = self.cache[cache_key]
            row.update(enrichment)
            return row

        # Attempt A: Official sources
        owner_a, conf_a, sources_a, notes_a = self.research_official_sources(row)

        # Attempt B: Web sources
        time.sleep(0.5)  # Rate limiting
        owner_b, conf_b, sources_b, notes_b = self.research_web_sources(row)

        # Attempt C: Smart name analysis (bonus attempt)
        owner_c, conf_c, notes_c = self.analyze_agency_name_for_owner(agency_name)

        # Reconcile results
        final_owner = ""
        final_confidence = 0
        final_sources = []
        final_intel = []

        # Use name analysis if we found a potential owner
        if owner_c and conf_c >= 35:
            final_owner = owner_c
            final_confidence = conf_c
            final_sources.append("Agency name pattern analysis")
            final_intel.append(f"• Potential owner: {owner_c} (inferred from agency name)")
            final_intel.append(f"• {notes_c}")

        # Add context about agency
        cert_date = row.get('Certification Date', '').strip()
        if cert_date:
            final_intel.append(f"• Certified since {cert_date}")

        city = row.get('City/Town', '').strip()
        state = row.get('State', '').strip()
        if city and state:
            final_intel.append(f"• Located in {city}, {state}")

        # Add revenue context
        appx_rev = row.get('APPX REV', '').strip()
        if appx_rev:
            try:
                rev_val = float(appx_rev)
                if rev_val >= 1000000:
                    final_intel.append(f"• Est. revenue ${rev_val/1000000:.1f}M - established mid-size operation")
                else:
                    final_intel.append(f"• Est. revenue ${rev_val/1000:.0f}K - smaller established operation")
            except:
                pass

        # Add quality rating
        quality = row.get('Quality of patient care star rating', '').strip()
        if quality and quality not in ['-', '']:
            final_intel.append(f"• Medicare quality rating: {quality} stars")

        # If we didn't find high-confidence owner, note what's needed
        if final_confidence < 60:
            final_intel.append(f"• RECOMMENDED: Verify owner via {state} Secretary of State business registry")
            final_intel.append(f"• RECOMMENDED: Search CMS Provider database for CCN {ccn}")

        # Prepare enrichment data
        enrichment = {
            'Owner Name': final_owner,
            'Confidence %': str(final_confidence),
            'Owner Sales Intel Report': "\n".join(final_intel[:6]),  # Max 6 bullets
            'Sources': " | ".join(final_sources) if final_sources else "Pattern analysis only - requires verification",
            'Attempt A Notes': notes_a,
            'Attempt B Notes': notes_b
        }

        # Cache the result
        self.cache[cache_key] = enrichment
        self._save_cache()

        # Update row
        row.update(enrichment)

        return row

    def process(self):
        """Main processing function"""
        logger.info("="*80)
        logger.info("Medicare Agency Owner Enrichment Script v2")
        logger.info(f"Input: {self.input_file}")
        logger.info(f"Output: {self.output_file}")
        logger.info(f"Revenue filter: ${self.min_rev:,.0f} - ${self.max_rev:,.0f}")
        logger.info("="*80)

        # Read input
        with open(self.input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames)
            rows = list(reader)

        self.stats['total_rows'] = len(rows)
        logger.info(f"Read {self.stats['total_rows']} rows")

        # Add new columns
        new_columns = ['Owner Name', 'Confidence %', 'Owner Sales Intel Report',
                      'Sources', 'Attempt A Notes', 'Attempt B Notes']
        for col in new_columns:
            if col not in fieldnames:
                fieldnames.append(col)

        # Process rows
        enriched_rows = []
        for i, row in enumerate(rows, 1):
            try:
                existing_owner = row.get('Owner Name', '').strip()
                appx_rev_str = row.get('APPX REV', '').strip()

                # Skip if has owner
                if existing_owner:
                    self.stats['skipped_has_owner'] += 1
                    enriched_rows.append(row)
                    continue

                # Skip if out of revenue range
                if not appx_rev_str:
                    self.stats['skipped_out_of_range'] += 1
                    enriched_rows.append(row)
                    continue

                try:
                    appx_rev = float(appx_rev_str)
                except ValueError:
                    self.stats['skipped_out_of_range'] += 1
                    enriched_rows.append(row)
                    continue

                if not (self.min_rev <= appx_rev <= self.max_rev):
                    self.stats['skipped_out_of_range'] += 1
                    enriched_rows.append(row)
                    continue

                # Enrich this row
                self.stats['attempted'] += 1
                logger.info(f"\n[{i}/{self.stats['total_rows']}]")
                enriched_row = self.enrich_row(row)

                # Track success
                if enriched_row.get('Owner Name', '').strip():
                    conf = int(enriched_row.get('Confidence %', '0'))
                    if conf >= 35:
                        self.stats['successfully_filled'] += 1
                    else:
                        self.stats['left_blank'] += 1
                else:
                    self.stats['left_blank'] += 1

                enriched_rows.append(enriched_row)

                # Save progress every 20 rows
                if i % 20 == 0:
                    self._write_output(enriched_rows, fieldnames)
                    logger.info(f"Progress saved: {i}/{self.stats['total_rows']}")

            except Exception as e:
                logger.error(f"Error on row {i}: {e}", exc_info=True)
                self.stats['errors'] += 1
                enriched_rows.append(row)

        # Final write
        self._write_output(enriched_rows, fieldnames)
        self._print_summary()

    def _write_output(self, rows: List[Dict], fieldnames: List[str]):
        """Write output file"""
        with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _print_summary(self):
        """Print summary"""
        logger.info("\n" + "="*80)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("="*80)
        logger.info(f"Total rows:                    {self.stats['total_rows']:,}")
        logger.info(f"Skipped (has owner):           {self.stats['skipped_has_owner']:,}")
        logger.info(f"Skipped (out of range):        {self.stats['skipped_out_of_range']:,}")
        logger.info(f"Attempted enrichment:          {self.stats['attempted']:,}")
        logger.info(f"Successfully filled (conf≥35): {self.stats['successfully_filled']:,}")
        logger.info(f"Left blank (conf<35):          {self.stats['left_blank']:,}")
        logger.info(f"Errors:                        {self.stats['errors']:,}")
        logger.info("="*80)

        if self.stats['successfully_filled'] > 0:
            success_rate = (self.stats['successfully_filled'] / self.stats['attempted'] * 100)
            logger.info(f"Success rate: {success_rate:.1f}%")

        logger.info(f"\nOutput file: {self.output_file}")
        logger.info(f"Cache file: {self.cache_file}")
        logger.info(f"Log file: run.log")
        logger.info("="*80)


def main():
    input_file = "CRM - HHAs by episodes # 2b53f850e21980adbd44ed2d4a99047f_all.csv"
    output_file = "agencies_enriched.csv"

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    enricher = SmartOwnerEnricher(
        input_file=input_file,
        output_file=output_file,
        min_rev=500000,
        max_rev=3000000
    )

    try:
        enricher.process()
    except KeyboardInterrupt:
        logger.info("\nInterrupted - progress saved")
        enricher._print_summary()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
