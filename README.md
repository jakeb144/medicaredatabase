# Medicare Agency Owner Enrichment Tool

Automated tool for enriching Medicare-certified home health agency data by researching and filling missing owner information.

## Overview

This tool processes a CSV of Medicare-certified agencies and enriches rows that:
- Have an APPX REV (approximate revenue) between $500,000 and $3,000,000
- Have an empty "Owner Name" field

For each qualifying agency, the tool performs:
1. **Attempt A**: Official source research (CMS, NPI registry, state business filings)
2. **Attempt B**: Web triangulation research (different query strategies)
3. **Reconciliation**: Compares both attempts and validates findings
4. **Confidence Scoring**: Assigns 0-100% confidence based on evidence quality
5. **Sales Intel Generation**: Creates 2-6 bullet point sales intelligence reports

## Files

- `enrich_owners.py` - Main enrichment script
- `requirements.txt` - Python dependencies (uses standard library only)
- `README.md` - This file
- `run.log` - Generated during execution (detailed logging)
- `enrichment_cache.json` - Generated during execution (prevents duplicate lookups)
- `agencies_enriched.csv` - Output file with enriched data

## Input CSV Columns Expected

The script automatically detects column name variations. Expected columns include:

**Required:**
- `Name` - Agency name
- `APPX REV` - Approximate revenue (filter: $500K-$3M)
- `Owner Name` - Will be filled if empty

**Useful for Research:**
- `CMS Certification Number (CCN)` - Medicare certification number
- `Address` - Street address
- `City/Town` - City
- `State` - State abbreviation
- `ZIP Code` - ZIP code
- `AAATelephone Number` - Phone number
- `Certification Date` - When agency was certified

## Output CSV Columns Added

The script adds/ensures these columns exist:

1. **Owner Name** - Filled only if originally blank and research succeeded
2. **Confidence %** - 0-100 score based on evidence strength:
   - 90-100: Multiple official sources agree
   - 70-89: Strong match from official + reputable sources
   - 40-69: Plausible but incomplete evidence
   - 0-39: Weak/uncertain/conflicting
3. **Owner Sales Intel Report** - 2-6 bullet points with:
   - Rapport hooks
   - Credibility indicators
   - Role/relationship to agency
   - Transition/succession signals (if any)
4. **Sources** - Compact source citations (max 5)
5. **Attempt A Notes** - Brief notes from official source research
6. **Attempt B Notes** - Brief notes from web triangulation

## How to Run

### Basic Usage

```bash
python3 enrich_owners.py
```

The script will:
1. Read `CRM - HHAs by episodes # 2b53f850e21980adbd44ed2d4a99047f_all.csv`
2. Process all qualifying rows (APPX REV $500K-$3M, no owner)
3. Generate `agencies_enriched.csv`
4. Create `run.log` with detailed progress
5. Create `enrichment_cache.json` to avoid duplicate lookups

### Resuming After Interruption

If the script is interrupted (Ctrl+C or crash), you can resume:
- The cache file prevents re-processing already researched agencies
- Progress is saved every 10 rows
- Simply re-run the script to continue

### Progress Monitoring

Watch the log in real-time:
```bash
tail -f run.log
```

## Configuration

Edit the script to change parameters:

```python
enricher = OwnerEnricher(
    input_file="your_file.csv",
    output_file="your_output.csv",
    min_rev=500000,   # Minimum revenue
    max_rev=3000000   # Maximum revenue
)
```

## Rate Limiting & Politeness

The script implements:
- 1-second delay between research attempts (prevents overwhelming servers)
- 2-second delay between retry attempts
- Caching to avoid duplicate lookups
- Progress saving every 10 rows

**If you encounter rate limiting or blocking:**
1. Increase delays in `enrich_owners.py` (search for `time.sleep()`)
2. Process in smaller batches by adjusting revenue range
3. Use a VPN or proxy if IP is blocked
4. Wait 1-24 hours and resume (cache will prevent re-processing)

## Research Methodology

### Attempt A: Official Sources First
1. CMS Certification Number (CCN) lookup
2. NPI (National Provider Identifier) registry search
3. State business registry (Secretary of State)
4. State licensure databases
5. Medicare provider directories

### Attempt B: Web Triangulation
1. Agency name + city/state searches
2. Address-based business lookups
3. Phone number reverse lookup
4. Corporate website "About" pages
5. LinkedIn company profiles
6. Press releases and news mentions
7. PPP loan data (if applicable)

### Reconciliation Logic
- If both attempts **agree**: Confidence +20%, proceed
- If both attempts **fail**: Leave blank, confidence 0%
- If attempts **disagree**: Retry up to 2 additional times
  - If still disagree: Choose highest confidence ≥40%, or leave blank

### Confidence Factors
Evidence strength is based on:
- **Official government filings** (highest weight)
- **NPI/CMS database matches** (high weight)
- **Multiple corroborating sources** (medium weight)
- **Single reputable source** (medium weight)
- **Directory listings only** (low weight)
- **Name consistency across sources** (increases confidence)
- **Address/phone matching** (increases confidence)

## Privacy & Compliance

The tool adheres to strict privacy standards:
- ✅ Uses only publicly available information
- ✅ Focuses on business owners/principals (not general staff)
- ✅ Includes business addresses from official filings
- ❌ Does NOT include: SSN, DOB, personal home addresses, sensitive personal data
- ❌ Does NOT scrape non-public databases
- ❌ Does NOT use deceptive practices to obtain data

**Legal basis**: All data collected is from publicly accessible sources (government registries, company websites, public business directories).

## Troubleshooting

### No Results / All Blank

**Cause**: Script cannot access web resources or databases
**Solution**:
- Verify internet connectivity
- Check if environment blocks web requests
- Review `run.log` for specific errors
- Consider implementing API integrations for CMS/NPI data

### Low Confidence Scores

**Cause**: Insufficient evidence or conflicting information
**Solution**:
- These require manual research
- Check state business registries directly
- Contact the agency directly
- Review Medicare provider enrollment data

### Script Errors

**Cause**: CSV format issues or missing columns
**Solution**:
- Ensure CSV has column headers
- Check encoding (should be UTF-8)
- Verify APPX REV column has numeric values
- Review `run.log` for specific error messages

## Output Interpretation

### Example Enriched Row

```csv
Name: "SUPERIOR HOME HEALTH SERVICES LLC"
Owner Name: "Jane Smith"
Confidence %: 85
Owner Sales Intel Report: "
• Listed as Managing Member in TX Secretary of State filing (2019)
• NPI registry shows authorized official matches owner name
• Agency certified since July 8, 2004
• Operating in McAllen, TX
• Est. revenue $1.2M - established operation
• Quality rating: 3 stars
"
Sources: "TX SOS Business Filing | NPI Registry | Medicare.gov"
Attempt A Notes: "Verified: CCN 453115 in CMS database | TX SOS: Jane Smith, Managing Member"
Attempt B Notes: "Website lists Jane Smith as Administrator | Address matches across sources"
```

### Confidence Interpretation

- **90-100%**: High confidence - multiple official sources agree, safe to use
- **70-89%**: Good confidence - verified by at least one official source
- **40-69%**: Moderate - plausible but verify before using
- **0-39%**: Low - conflicting or weak evidence, requires manual review

## Statistics Output

After completion, the script prints:

```
ENRICHMENT SUMMARY
Total rows processed:          1,830
Rows skipped (has owner):      825
Rows skipped (out of range):   578
Rows attempted:                427
Rows successfully filled:      245
Rows left blank:               182
Errors:                        0
```

## Notes

- **Processing time**: Approximately 1-2 seconds per agency (with rate limiting)
- **Expected success rate**: 50-70% depending on data quality and web availability
- **Cache benefits**: Duplicate agencies are instant on second run
- **Incremental progress**: Safe to interrupt and resume

## Support

For issues or questions:
1. Check `run.log` for detailed error messages
2. Review this README troubleshooting section
3. Verify input CSV format matches expected structure
4. Ensure internet connectivity for research capabilities

## Version

Version: 1.0.0
Last Updated: 2026-01-17
