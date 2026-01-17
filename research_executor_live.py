#!/usr/bin/env python3
"""
Live Research Executor
This script coordinates the execution of web research for all agencies
It outputs research commands that can be executed via the WebSearch tool
"""

import json
import os

def load_research_plan():
    """Load the research plan"""
    with open('RESEARCH_PLAN.json', 'r') as f:
        return json.load(f)

def create_execution_queue(max_agencies=None):
    """
    Create an execution queue - list of all research tasks
    """
    plan = load_research_plan()
    agencies = plan['agencies']

    if max_agencies:
        agencies = agencies[:max_agencies]

    execution_queue = []

    for i, agency_plan in enumerate(agencies):
        agency = agency_plan['info']
        queries = agency_plan['queries']

        task = {
            'agency_index': i + 1,
            'total_agencies': len(agencies),
            'ccn': agency['ccn'],
            'agency_name': agency['name'],
            'agency_info': agency,
            'research_tasks': []
        }

        # Attempt A queries (official sources)
        for idx, query in enumerate(queries['attempt_a_official'], 1):
            task['research_tasks'].append({
                'type': 'attempt_a',
                'query_number': idx,
                'query': query,
                'purpose': 'Official source verification'
            })

        # Attempt B queries (web triangulation)
        for idx, query in enumerate(queries['attempt_b_web'], 1):
            task['research_tasks'].append({
                'type': 'attempt_b',
                'query_number': idx,
                'query': query,
                'purpose': 'Web triangulation'
            })

        execution_queue.append(task)

    return execution_queue

def main():
    # Create full execution queue
    print("Creating execution queue for ALL 427 agencies...")
    queue = create_execution_queue()

    # Save queue
    with open('EXECUTION_QUEUE_FULL.json', 'w') as f:
        json.dump(queue, f, indent=2)

    print(f"\n✓ Execution queue created")
    print(f"  - Total agencies: {len(queue)}")
    print(f"  - Total research tasks: {sum(len(task['research_tasks']) for task in queue)}")
    print(f"  - Saved to: EXECUTION_QUEUE_FULL.json")

    # Also create a smaller sample queue for testing
    print("\nCreating sample queue (first 10 agencies)...")
    sample_queue = create_execution_queue(max_agencies=10)

    with open('EXECUTION_QUEUE_SAMPLE.json', 'w') as f:
        json.dump(sample_queue, f, indent=2)

    print(f"✓ Sample queue created")
    print(f"  - Sample agencies: {len(sample_queue)}")
    print(f"  - Saved to: EXECUTION_QUEUE_SAMPLE.json")

    print("\n" + "="*80)
    print("READY FOR WEB RESEARCH EXECUTION")
    print("="*80)
    print("\nThe execution queue is ready.")
    print("Next: Execute web searches for all agencies in the queue.")

if __name__ == "__main__":
    main()
