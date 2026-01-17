#!/usr/bin/env python3
"""
Research Executor - Generates executable research commands
This creates a structured list of all web searches that need to be performed
"""

import csv
import json
import os
from datetime import datetime

def generate_research_plan():
    """Generate a complete research plan with all queries"""

    input_file = "CRM - HHAs by episodes # 2b53f850e21980adbd44ed2d4a99047f_all.csv"

    # Read and filter agencies
    agencies_to_research = []

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            existing_owner = row.get('Owner Name', '').strip()
            appx_rev_str = row.get('APPX REV', '').strip()

            if existing_owner or not appx_rev_str:
                continue

            try:
                appx_rev = float(appx_rev_str)
                if not (500000 <= appx_rev <= 3000000):
                    continue
            except ValueError:
                continue

            agencies_to_research.append({
                'ccn': row.get('CMS Certification Number (CCN)', '').strip(),
                'name': row.get('Name', '').strip(),
                'city': row.get('City/Town', '').strip(),
                'state': row.get('State', '').strip(),
                'address': row.get('Address', '').strip(),
                'phone': row.get('AAATelephone Number', '').strip(),
                'revenue': appx_rev_str,
                'cert_date': row.get('Certification Date', '').strip()
            })

    # Generate research queries for each agency
    research_plan = {
        'generated_at': datetime.now().isoformat(),
        'total_agencies': len(agencies_to_research),
        'agencies': []
    }

    for agency in agencies_to_research:
        queries = {
            'attempt_a_official': [
                f'NPI registry "{agency["name"]}" {agency["city"]} {agency["state"]} authorized official owner',
                f'{agency["state"]} Secretary of State business search "{agency["name"]}" managing member owner',
                f'CMS certification {agency["ccn"]} provider owner administrator'
            ],
            'attempt_b_web': [
                f'"{agency["name"]}" {agency["city"]} {agency["state"]} owner CEO administrator founder',
                f'"{agency["address"]}" {agency["city"]} business owner registration',
                f'"{agency["name"]}" home health about leadership management team'
            ]
        }

        research_plan['agencies'].append({
            'info': agency,
            'queries': queries
        })

    # Save plan
    with open('RESEARCH_PLAN.json', 'w') as f:
        json.dump(research_plan, f, indent=2)

    print(f"Generated research plan for {len(agencies_to_research)} agencies")
    print(f"Total queries to execute: {len(agencies_to_research) * 6}")
    print(f"Saved to: RESEARCH_PLAN.json")

    return research_plan

if __name__ == "__main__":
    generate_research_plan()
