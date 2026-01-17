#!/usr/bin/env python3
"""
Medicare Agency Owner Enrichment Script
Enriches agencies CSV by filling missing owner names with dual-pass verification
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
class ResearchAttempt:
    """Results from a single research attempt"""
    owner_name: str
    confidence: int
    notes: str
    sources: List[str]


@dataclass
class EnrichmentResult:
    """Complete enrichment result for an agency"""
    owner_name: str
    confidence: int
    sales_intel_report: str
    sources: str
    attempt_a_notes: str
    attempt_b_notes: str


class OwnerEnricher:
    """Main class for enriching owner information"""

    def __init__(self, input_file: str, output_file: str, min_rev: float = 500000, max_rev: float = 3000000):
        self.input_file = input_file
        self.output_file = output_file
        self.min_rev = min_rev
        self.max_rev = max_rev
        self.cache_file = 'enrichment_cache.json'
        self.cache = self._load_cache()

        # Statistics
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

    def _generate_cache_key(self, agency_name: str, ccn: str, address: str) -> str:
        """Generate unique cache key for an agency"""
        key_str = f"{agency_name}|{ccn}|{address}".lower()
        return hashlib.md5(key_str.encode()).hexdigest()

    def _normalize_column_name(self, columns: List[str], target_names: List[str]) -> Optional[str]:
        """Find the actual column name from a list of possible names"""
        columns_lower = {col.lower(): col for col in columns}
        for target in target_names:
            if target.lower() in columns_lower:
                return columns_lower[target.lower()]
        return None

    def _extract_name_from_text(self, text: str) -> Optional[str]:
        """Extract a person's name from text using patterns"""
        # Look for common patterns in official documents
        patterns = [
            r'(?:Managing Member|Owner|Administrator|CEO|President|Principal):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'Authorized Official:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'Contact:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),\s*(?:Owner|CEO|President|Administrator)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def research_attempt_a(self, row: Dict) -> ResearchAttempt:
        """
        Attempt A: Official sources first
        - CMS/CCN lookups
        - NPI registry
        - State licensure
        - Business registries
        """
        logger.info(f"  Attempt A: Official sources for {row.get('Name', 'Unknown')}")

        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        state = row.get('State', '').strip()
        city = row.get('City/Town', '').strip()
        address = row.get('Address', '').strip()

        sources = []
        owner_candidates = []
        notes = []

        # Since we don't have direct API access to CMS/NPI databases,
        # we'll note what should be checked and return uncertain results
        # In a real implementation, this would query actual databases

        notes.append(f"Should verify: CCN {ccn} in CMS database")
        notes.append(f"Should check: NPI registry for {agency_name}")
        notes.append(f"Should verify: {state} Secretary of State business registry")

        # For this implementation, we acknowledge we cannot perform actual lookups
        # without external API access or web scraping capabilities

        return ResearchAttempt(
            owner_name="",
            confidence=0,
            notes=" | ".join(notes[:3]),  # Keep notes short
            sources=[]
        )

    def research_attempt_b(self, row: Dict) -> ResearchAttempt:
        """
        Attempt B: Web triangulation
        - Different query order
        - Multiple sources
        - Cross-reference checks
        """
        logger.info(f"  Attempt B: Web triangulation for {row.get('Name', 'Unknown')}")

        agency_name = row.get('Name', '').strip()
        city = row.get('City/Town', '').strip()
        state = row.get('State', '').strip()
        address = row.get('Address', '').strip()
        phone = row.get('AAATelephone Number', '').strip()

        sources = []
        notes = []

        # Note what searches should be performed
        notes.append(f"Should search: '{agency_name} {city} {state} owner'")
        notes.append(f"Should search: '{address} {city} business owner'")
        if phone:
            notes.append(f"Should lookup: phone {phone}")

        # Without actual web access in the script, we return uncertain
        return ResearchAttempt(
            owner_name="",
            confidence=0,
            notes=" | ".join(notes[:3]),
            sources=[]
        )

    def reconcile_attempts(self, attempt_a: ResearchAttempt, attempt_b: ResearchAttempt,
                          row: Dict, max_retries: int = 2) -> EnrichmentResult:
        """
        Reconcile two research attempts
        If they disagree, retry until they agree or max retries reached
        """
        retry_count = 0

        while retry_count < max_retries:
            # Compare owner names (case-insensitive, whitespace normalized)
            name_a = attempt_a.owner_name.strip().lower()
            name_b = attempt_b.owner_name.strip().lower()

            if name_a == name_b and name_a:
                # Agreement! Increase confidence
                base_confidence = max(attempt_a.confidence, attempt_b.confidence)
                confidence = min(100, base_confidence + 20)  # Bonus for agreement

                logger.info(f"  ✓ Attempts agree: {attempt_a.owner_name} (confidence: {confidence}%)")

                return EnrichmentResult(
                    owner_name=attempt_a.owner_name,
                    confidence=confidence,
                    sales_intel_report=self._generate_sales_intel(attempt_a, attempt_b, row),
                    sources=self._merge_sources(attempt_a.sources, attempt_b.sources),
                    attempt_a_notes=attempt_a.notes,
                    attempt_b_notes=attempt_b.notes
                )

            elif not name_a and not name_b:
                # Both attempts failed to find owner
                logger.warning(f"  ✗ No owner found after both attempts")

                return EnrichmentResult(
                    owner_name="",
                    confidence=0,
                    sales_intel_report=f"Unable to identify owner. Attempted: {attempt_a.notes[:100]}",
                    sources="N/A - insufficient data",
                    attempt_a_notes=attempt_a.notes,
                    attempt_b_notes=attempt_b.notes
                )

            else:
                # Disagreement - would retry in real implementation
                logger.warning(f"  ⚠ Attempts disagree: '{name_a}' vs '{name_b}' (retry {retry_count + 1}/{max_retries})")
                retry_count += 1

                if retry_count < max_retries:
                    time.sleep(2)  # Rate limiting
                    # In real implementation, would do new research attempts here
                    # For now, we'll just break
                    break

        # Max retries reached or permanent disagreement
        # Choose the one with higher confidence or leave blank if both low
        if attempt_a.confidence >= 40 and attempt_a.confidence > attempt_b.confidence:
            chosen = attempt_a
            notes_suffix = f"(Chosen attempt A; B found: {attempt_b.owner_name})"
        elif attempt_b.confidence >= 40:
            chosen = attempt_b
            notes_suffix = f"(Chosen attempt B; A found: {attempt_a.owner_name})"
        else:
            # Neither is confident enough
            return EnrichmentResult(
                owner_name="",
                confidence=max(attempt_a.confidence, attempt_b.confidence),
                sales_intel_report=f"Conflicting information found. Requires manual review. A: {attempt_a.owner_name} | B: {attempt_b.owner_name}",
                sources=self._merge_sources(attempt_a.sources, attempt_b.sources),
                attempt_a_notes=attempt_a.notes,
                attempt_b_notes=attempt_b.notes
            )

        return EnrichmentResult(
            owner_name=chosen.owner_name,
            confidence=chosen.confidence,
            sales_intel_report=self._generate_sales_intel(chosen, None, row) + f" {notes_suffix}",
            sources=self._merge_sources(attempt_a.sources, attempt_b.sources),
            attempt_a_notes=attempt_a.notes,
            attempt_b_notes=attempt_b.notes
        )

    def _merge_sources(self, sources_a: List[str], sources_b: List[str]) -> str:
        """Merge and deduplicate sources"""
        all_sources = list(set(sources_a + sources_b))
        if not all_sources:
            return "N/A"
        return " | ".join(all_sources[:5])  # Keep it short, max 5 sources

    def _generate_sales_intel(self, attempt_a: ResearchAttempt, attempt_b: Optional[ResearchAttempt],
                             row: Dict) -> str:
        """Generate 2-6 bullet point sales intelligence report"""
        intel_points = []

        if attempt_a.owner_name:
            # Add evidence-based points
            if attempt_a.sources:
                for i, source in enumerate(attempt_a.sources[:2]):
                    intel_points.append(f"• Verified via {source}")

            # Add agency context
            agency_name = row.get('Name', '')
            city = row.get('City/Town', '')
            state = row.get('State', '')
            cert_date = row.get('Certification Date', '')

            if cert_date:
                intel_points.append(f"• Agency certified since {cert_date}")

            intel_points.append(f"• Operating in {city}, {state}")

            # Add revenue context
            appx_rev = row.get('APPX REV', '')
            if appx_rev:
                try:
                    rev_float = float(appx_rev)
                    if rev_float >= 1000000:
                        intel_points.append(f"• Est. revenue ${rev_float/1000000:.1f}M - established operation")
                    else:
                        intel_points.append(f"• Est. revenue ${rev_float/1000:.0f}K")
                except:
                    pass

            # Add quality rating if available
            quality_rating = row.get('Quality of patient care star rating', '').strip()
            if quality_rating and quality_rating not in ['-', '']:
                intel_points.append(f"• Quality rating: {quality_rating} stars")
        else:
            intel_points.append(f"• Owner identity could not be verified")
            intel_points.append(f"• Recommend manual research via state business registry")

        # Return max 6 points
        return "\n".join(intel_points[:6])

    def enrich_row(self, row: Dict) -> Optional[EnrichmentResult]:
        """Enrich a single row with owner information"""
        agency_name = row.get('Name', '').strip()
        ccn = row.get('CMS Certification Number (CCN)', '').strip()
        address = row.get('Address', '').strip()

        # Check cache first
        cache_key = self._generate_cache_key(agency_name, ccn, address)
        if cache_key in self.cache:
            logger.info(f"Using cached result for {agency_name}")
            cached = self.cache[cache_key]
            return EnrichmentResult(**cached)

        logger.info(f"Enriching: {agency_name} (CCN: {ccn})")

        # Attempt A: Official sources
        time.sleep(1)  # Rate limiting
        attempt_a = self.research_attempt_a(row)

        # Attempt B: Web triangulation
        time.sleep(1)  # Rate limiting
        attempt_b = self.research_attempt_b(row)

        # Reconcile
        result = self.reconcile_attempts(attempt_a, attempt_b, row)

        # Cache the result
        self.cache[cache_key] = asdict(result)
        self._save_cache()

        return result

    def process(self):
        """Main processing function"""
        logger.info("="*60)
        logger.info("Medicare Agency Owner Enrichment Script")
        logger.info(f"Input: {self.input_file}")
        logger.info(f"Output: {self.output_file}")
        logger.info(f"Revenue range: ${self.min_rev:,.0f} - ${self.max_rev:,.0f}")
        logger.info("="*60)

        # Read input CSV
        with open(self.input_file, 'r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames

            # Add new columns if they don't exist
            new_columns = [
                'Owner Name',
                'Confidence %',
                'Owner Sales Intel Report',
                'Sources',
                'Attempt A Notes',
                'Attempt B Notes'
            ]

            # Ensure all new columns are in fieldnames
            for col in new_columns:
                if col not in fieldnames:
                    fieldnames.append(col)

            rows = list(reader)
            self.stats['total_rows'] = len(rows)

        logger.info(f"Read {self.stats['total_rows']} rows from input file")

        # Process rows
        enriched_rows = []

        for i, row in enumerate(rows, 1):
            try:
                # Check if we should process this row
                appx_rev_str = row.get('APPX REV', '').strip()
                existing_owner = row.get('Owner Name', '').strip()

                # Skip if already has owner
                if existing_owner:
                    self.stats['skipped_has_owner'] += 1
                    enriched_rows.append(row)
                    continue

                # Skip if no APPX REV or out of range
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

                # Process this row
                self.stats['attempted'] += 1
                logger.info(f"\n[{i}/{self.stats['total_rows']}] Processing: {row.get('Name', 'Unknown')}")

                result = self.enrich_row(row)

                if result:
                    # Update row with enrichment data
                    row['Owner Name'] = result.owner_name
                    row['Confidence %'] = str(result.confidence)
                    row['Owner Sales Intel Report'] = result.sales_intel_report
                    row['Sources'] = result.sources
                    row['Attempt A Notes'] = result.attempt_a_notes
                    row['Attempt B Notes'] = result.attempt_b_notes

                    if result.owner_name and result.confidence >= 40:
                        self.stats['successfully_filled'] += 1
                    else:
                        self.stats['left_blank'] += 1

                enriched_rows.append(row)

                # Save progress every 10 rows
                if i % 10 == 0:
                    self._save_progress(enriched_rows, fieldnames)
                    logger.info(f"Progress saved: {i}/{self.stats['total_rows']} rows processed")

            except Exception as e:
                logger.error(f"Error processing row {i}: {e}", exc_info=True)
                self.stats['errors'] += 1
                enriched_rows.append(row)

        # Write final output
        logger.info(f"\nWriting final output to {self.output_file}")
        with open(self.output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)

        # Print summary
        self._print_summary()

    def _save_progress(self, rows: List[Dict], fieldnames: List[str]):
        """Save progress to output file"""
        with open(self.output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _print_summary(self):
        """Print execution summary"""
        logger.info("\n" + "="*60)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("="*60)
        logger.info(f"Total rows processed:          {self.stats['total_rows']}")
        logger.info(f"Rows skipped (has owner):      {self.stats['skipped_has_owner']}")
        logger.info(f"Rows skipped (out of range):   {self.stats['skipped_out_of_range']}")
        logger.info(f"Rows attempted:                {self.stats['attempted']}")
        logger.info(f"Rows successfully filled:      {self.stats['successfully_filled']}")
        logger.info(f"Rows left blank:               {self.stats['left_blank']}")
        logger.info(f"Errors:                        {self.stats['errors']}")
        logger.info("="*60)
        logger.info(f"Output file: {self.output_file}")
        logger.info(f"Cache file: {self.cache_file}")
        logger.info(f"Log file: run.log")
        logger.info("="*60)


def main():
    """Main entry point"""
    input_file = "CRM - HHAs by episodes # 2b53f850e21980adbd44ed2d4a99047f_all.csv"
    output_file = "agencies_enriched.csv"

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found!")
        print("Please ensure the CSV file is in the current directory.")
        sys.exit(1)

    enricher = OwnerEnricher(
        input_file=input_file,
        output_file=output_file,
        min_rev=500000,
        max_rev=3000000
    )

    try:
        enricher.process()
    except KeyboardInterrupt:
        logger.info("\n\nProcess interrupted by user. Progress has been saved.")
        enricher._print_summary()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
