#!/usr/bin/env python3
"""
Instagram Tracker - GitHub Actions Version
Tracks PUBLIC Instagram accounts and updates Airtable
No Instagram login required - completely free!
"""

import os
import json
import time
from datetime import datetime, timedelta
import pytz
import instaloader
from pyairtable import Api

class InstagramTracker:
    """Main tracker class"""
    
    def __init__(self):
        # Configuration from environment variables
        self.airtable_token = os.environ.get('AIRTABLE_TOKEN')
        self.airtable_base_id = os.environ.get('AIRTABLE_BASE_ID', 'appqblRpkPud9ywI9')
        self.airtable_table_id = os.environ.get('AIRTABLE_TABLE_ID', 'tbl4Jx1Km6vvzeqrQ')
        self.melbourne_tz = pytz.timezone('Australia/Melbourne')
        
        # Initialize clients
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern=''
        )
        
        # Initialize Airtable - using table ID instead of name
        self.api = Api(self.airtable_token)
        self.table = self.api.table(self.airtable_base_id, self.airtable_table_id)
    
    def extract_username_from_url(self, url):
        """Extract username from Instagram URL"""
        import re
        if not url:
            return None
        match = re.search(r'instagram\.com/([^/?\\s]+)', url)
        if match:
            return match.group(1)
        return None
    
    def get_active_accounts(self):
        """Fetch active accounts from Airtable"""
        print("📥 Fetching active accounts from Airtable...")
        
        try:
            all_records = self.table.all()
            active_accounts = []
            
            for record in all_records:
                fields = record['fields']
                
                # Filter: Status must be "Active"
                if fields.get('Status') != 'Active':
                    continue
                
                # Get username from IG User (priority) or IG URL (fallback)
                ig_user = fields.get('IG User', '').strip()
                ig_url = fields.get('IG URL', '').strip()
                
                username = None
                # Try IG User column first (most reliable)
                if ig_user:
                    username = ig_user.lstrip('@')
                # Fall back to extracting from URL if IG User is empty
                elif ig_url:
                    username = self.extract_username_from_url(ig_url)
                
                if not username:
                    continue
                
                active_accounts.append({
                    'record_id': record['id'],
                    'username': username,
                    'model_name': fields.get('Model', 'Unknown')
                })
            
            print(f"✅ Found {len(active_accounts)} active accounts to track")
            return active_accounts
            
        except Exception as e:
            print(f"❌ Error fetching Airtable records: {e}")
            return []
    
    def get_instagram_data(self, username):
        """
        Get Instagram profile data (public accounts only)
        Returns: dict with follower_count, posts_today, last_post_time, error
        """
        try:
            print(f"  Fetching data for @{username}...")
            
            # Load profile
            profile = instaloader.Profile.from_username(self.loader.context, username)
            
            # Check if private
            if profile.is_private:
                print(f"  ⚠️  @{username} is PRIVATE - setting to 11")
                return {
                    'follower_count': 11,
                    'posts_today': 0,
                    'last_post_time': None,
                    'error': 'private'
                }
            
            # Get follower count
            follower_count = profile.followers
            
            # Get posts from last 24 hours
            now_melbourne = datetime.now(self.melbourne_tz)
            midnight_melbourne = now_melbourne.replace(hour=0, minute=0, second=0, microsecond=0)
            
            posts_today = 0
            last_post_time = None
            
            # Iterate through recent posts
            for post in profile.get_posts():
                # Convert post time to Melbourne timezone
                post_time_utc = post.date_utc
                if post_time_utc.tzinfo is None:
                    post_time_utc = pytz.utc.localize(post_time_utc)
                
                post_time_melbourne = post_time_utc.astimezone(self.melbourne_tz)
                
                # Track last post time
                if last_post_time is None:
                    last_post_time = post_time_melbourne
                
                # Count posts since midnight Melbourne
                if post_time_melbourne >= midnight_melbourne:
                    posts_today += 1
                else:
                    # Posts are in reverse chronological order, so we can stop
                    break
            
            return {
                'follower_count': follower_count,
                'posts_today': posts_today,
                'last_post_time': last_post_time,
                'error': None
            }
            
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"  ⚠️  @{username} NOT FOUND - setting to 11")
            return {
                'follower_count': 11,
                'posts_today': 0,
                'last_post_time': None,
                'error': 'not_found'
            }
        
        except instaloader.exceptions.ConnectionException as e:
            print(f"  ⚠️  @{username} CONNECTION ERROR - skipping")
            return {
                'follower_count': 0,
                'posts_today': 0,
                'last_post_time': None,
                'error': 'connection'
            }
        
        except Exception as e:
            print(f"  ❌ Error fetching @{username}: {e}")
            return {
                'follower_count': 11,
                'posts_today': 0,
                'last_post_time': None,
                'error': 'unknown'
            }
    
    def update_airtable(self, record_id, data):
        """Update Airtable record"""
        try:
            update_data = {
                "Posted today": data['posts_today'],
                "Insta Followers": data['follower_count']
            }
            
            if data['last_post_time']:
                update_data["Last Posted"] = data['last_post_time'].isoformat()
            
            self.table.update(record_id, update_data)
            return True
            
        except Exception as e:
            print(f"  ❌ Error updating Airtable: {e}")
            return False
    
    def track_account(self, account):
        """Track single account"""
        username = account['username']
        model_name = account['model_name']
        record_id = account['record_id']
        
        print(f"\n📊 Tracking: {model_name} (@{username})")
        
        # Get Instagram data
        data = self.get_instagram_data(username)
        
        # Handle errors
        if data['error'] and data['error'] != 'connection':
            # Update with error indicator (11)
            self.update_airtable(record_id, data)
            print(f"  ⚠️  Set to 11 due to: {data['error']}")
            return
        
        if data['error'] == 'connection':
            # Skip connection errors - will retry next run
            print(f"  ⏭️  Skipped due to connection error")
            return
        
        # Update Airtable with data
        if self.update_airtable(record_id, data):
            print(f"  ✅ Updated: {data['posts_today']} posts today, {data['follower_count']:,} followers")
        
        # Be nice to Instagram - add delay between accounts
        time.sleep(2)
    
    def run(self):
        """Main tracking function"""
        print("=" * 60)
        print("🚀 Instagram Tracker - GitHub Actions")
        print("=" * 60)
        
        now_melbourne = datetime.now(self.melbourne_tz)
        print(f"⏰ Run time: {now_melbourne.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Get accounts to track
        accounts = self.get_active_accounts()
        
        if not accounts:
            print("⚠️  No active accounts found")
            return
        
        # Track each account
        success_count = 0
        error_count = 0
        
        for account in accounts:
            try:
                self.track_account(account)
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to track {account['username']}: {e}")
                error_count += 1
        
        print("\n" + "=" * 60)
        print(f"✅ Tracking complete!")
        print(f"   Success: {success_count} accounts")
        print(f"   Errors: {error_count} accounts")
        print("=" * 60)


if __name__ == "__main__":
    # Check for required environment variables
    if not os.environ.get('AIRTABLE_TOKEN'):
        print("❌ ERROR: AIRTABLE_TOKEN environment variable not set!")
        exit(1)
    
    # Run tracker
    tracker = InstagramTracker()
    tracker.run()
