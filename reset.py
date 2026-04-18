#!/usr/bin/env python3
"""
Daily Reset Script
Resets "Posted Today" to 0 at midnight Melbourne time
"""

import os
from datetime import datetime
import pytz
from pyairtable import Api

def main():
    """Reset Posted Today counts"""
    print("=" * 60)
    print("🔄 Daily Reset - Instagram Tracker")
    print("=" * 60)
    
    # Get current Melbourne time
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now_melbourne = datetime.now(melbourne_tz)
    print(f"⏰ Reset time: {now_melbourne.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Get Airtable credentials
    airtable_token = os.environ.get('AIRTABLE_TOKEN')
    airtable_base_id = os.environ.get('AIRTABLE_BASE_ID', 'appqblRpkPud9ywI9')
    airtable_table_id = os.environ.get('AIRTABLE_TABLE_ID', 'tbl4Jx1Km6vvzeqrQ')
    
    if not airtable_token:
        print("❌ ERROR: AIRTABLE_TOKEN not set!")
        exit(1)
    
    # Initialize Airtable - using table ID instead of name
    print("\n📥 Connecting to Airtable...")
    api = Api(airtable_token)
    table = api.table(airtable_base_id, airtable_table_id)
    
    # Get all records
    print("📋 Fetching all records...")
    all_records = table.all()
    print(f"   Found {len(all_records)} records")
    
    # Reset Posted today to 0
    print("\n🔄 Resetting 'Posted today' to 0...")
    updated_count = 0
    
    for record in all_records:
        try:
            table.update(record['id'], {"Posted today": 0})
            updated_count += 1
        except Exception as e:
            print(f"   ⚠️  Failed to reset {record['id']}: {e}")
    
    print(f"   ✅ Reset {updated_count} records")
    
    print("\n" + "=" * 60)
    print("✅ Daily reset complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
