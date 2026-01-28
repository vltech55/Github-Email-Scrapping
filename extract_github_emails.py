#!/usr/bin/env python3
"""
Standalone GitHub Email Extractor
Extracts personal emails from GitHub profiles and commit history.
Uses same methods as the main project.
"""

import os
import time
import requests
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class GitHubEmailExtractor:
    """Extract emails from GitHub profiles and commits."""
    
    def __init__(self, github_token: Optional[str] = None):
        """Initialize with GitHub token."""
        self.token = github_token or os.getenv('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("GitHub token required! Set GITHUB_TOKEN in .env or pass as argument")
        
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_profile_email(self, username: str) -> Optional[str]:
        """
        Get email from GitHub profile (if public).
        
        Args:
            username: GitHub username
            
        Returns:
            Email address or None
        """
        try:
            url = f'https://api.github.com/users/{username}'
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                email = data.get('email')
                if email and '@' in email and 'noreply' not in email.lower():
                    return email
            
            return None
            
        except Exception as e:
            print(f"Error getting profile for {username}: {e}")
            return None
    
    def get_user_repositories(self, username: str, max_repos: int = 5) -> List[Dict]:
        """
        Get user's repositories (non-fork, recently pushed).
        
        Args:
            username: GitHub username
            max_repos: Maximum number of repos to return
            
        Returns:
            List of repository data
        """
        try:
            # Fetch more repos to allow for filtering
            url = f'https://api.github.com/users/{username}/repos'
            params = {
                'sort': 'pushed',  # Recently active repos
                'direction': 'desc',
                'per_page': max_repos * 2  # Fetch extra for filtering
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                all_repos = response.json()
                
                # Filter out forks, prioritize own repos
                own_repos = [r for r in all_repos if not r.get('fork', False)]
                
                # Return own repos first, then forks if needed
                if own_repos:
                    return own_repos[:max_repos]
                else:
                    return all_repos[:max_repos]
            
            return []
            
        except Exception as e:
            print(f"Error getting repos for {username}: {e}")
            return []
    
    def get_commit_emails(self, username: str, repo_name: str, max_commits: int = 30) -> Set[str]:
        """
        Get emails from recent commits in a repository.
        
        Args:
            username: GitHub username (repo owner)
            repo_name: Repository name
            max_commits: Maximum commits to check
            
        Returns:
            Set of email addresses found
        """
        emails = set()
        
        try:
            url = f'https://api.github.com/repos/{username}/{repo_name}/commits'
            params = {
                'author': username,  # Only commits by this user
                'per_page': max_commits
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                commits = response.json()
                
                for commit in commits:
                    try:
                        # Check commit author
                        author = commit.get('commit', {}).get('author', {})
                        email = author.get('email', '').strip()
                        
                        # Validate email
                        if email and '@' in email:
                            email_lower = email.lower()
                            # Filter out GitHub no-reply and invalid emails
                            if not any(bad in email_lower for bad in [
                                'noreply', 'github.com', 'example.com', 
                                'test.com', 'localhost'
                            ]):
                                emails.add(email)
                        
                        # Also check committer (might be different)
                        committer = commit.get('commit', {}).get('committer', {})
                        email = committer.get('email', '').strip()
                        
                        if email and '@' in email:
                            email_lower = email.lower()
                            if not any(bad in email_lower for bad in [
                                'noreply', 'github.com', 'example.com',
                                'test.com', 'localhost'
                            ]):
                                emails.add(email)
                                
                    except Exception:
                        continue
            
            return emails
            
        except Exception as e:
            print(f"Error getting commits for {username}/{repo_name}: {e}")
            return emails
    
    def extract_all_emails(self, username: str, max_repos: int = 3) -> Dict:
        """
        Extract all possible emails for a GitHub user.
        Checks profile and multiple repositories.
        
        Args:
            username: GitHub username
            max_repos: Maximum repositories to check
            
        Returns:
            dict with:
                - success: bool
                - username: str
                - emails: list of emails found
                - sources: dict mapping emails to their sources
                - api_calls_used: int
        """
        print(f"\n{'='*60}")
        print(f"Extracting emails for: {username}")
        print(f"{'='*60}")
        
        result = {
            'success': False,
            'username': username,
            'emails': [],
            'sources': {},
            'api_calls_used': 0
        }
        
        api_calls = 0
        all_emails = set()
        sources = {}
        
        # Step 1: Check profile
        print(f"[1/2] Checking profile...")
        profile_email = self.get_profile_email(username)
        api_calls += 1
        
        if profile_email:
            print(f"  ✓ Found in profile: {profile_email}")
            all_emails.add(profile_email)
            sources[profile_email] = 'profile'
        else:
            print(f"  - No email in profile")
        
        # Step 2: Check commit history in repositories
        print(f"[2/2] Checking commit history (up to {max_repos} repos)...")
        repos = self.get_user_repositories(username, max_repos=max_repos)
        api_calls += 1
        
        if not repos:
            print(f"  - No repositories found")
        else:
            print(f"  Found {len(repos)} repositories")
            
            for i, repo in enumerate(repos, 1):
                repo_name = repo['name']
                is_fork = repo.get('fork', False)
                fork_tag = " [FORK]" if is_fork else ""
                
                print(f"  [{i}/{len(repos)}] Checking {repo_name}{fork_tag}...")
                
                commit_emails = self.get_commit_emails(username, repo_name)
                api_calls += 1
                
                if commit_emails:
                    for email in commit_emails:
                        if email not in all_emails:
                            print(f"    ✓ Found: {email}")
                            all_emails.add(email)
                            sources[email] = f'commits:{repo_name}'
                        else:
                            print(f"    - Duplicate: {email}")
                else:
                    print(f"    - No emails found")
                
                # Small delay between repos
                time.sleep(0.3)
        
        # Prepare result
        result['success'] = len(all_emails) > 0
        result['emails'] = sorted(list(all_emails))
        result['sources'] = sources
        result['api_calls_used'] = api_calls
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"SUMMARY for {username}")
        print(f"{'='*60}")
        print(f"Emails found: {len(all_emails)}")
        
        if all_emails:
            for email in sorted(all_emails):
                source = sources.get(email, 'unknown')
                print(f"  • {email} (from {source})")
        else:
            print(f"  No emails found")
        
        print(f"\nAPI calls used: {api_calls}")
        print(f"{'='*60}\n")
        
        return result


def main():
    """Main function to run the extractor."""
    
    print("="*60)
    print("GitHub Email Extractor")
    print("="*60)
    print()
    
    # Initialize extractor
    try:
        extractor = GitHubEmailExtractor()
        print(f"✓ GitHub token loaded")
    except ValueError as e:
        print(f"✗ Error: {e}")
        print("\nPlease set GITHUB_TOKEN in .env file or environment variable")
        return
    
    print()
    
    # Get username from user
    username = input("Enter GitHub username to extract emails: ").strip()
    
    if not username:
        print("No username provided!")
        return
    
    # Ask for max repos
    try:
        max_repos = input("Max repositories to check (default 3): ").strip()
        max_repos = int(max_repos) if max_repos else 3
    except ValueError:
        max_repos = 3
    
    # Extract emails
    result = extractor.extract_all_emails(username, max_repos=max_repos)
    
    # Print result
    if result['success']:
        print(f"\n✓ SUCCESS! Found {len(result['emails'])} email(s)")
        
        # Save to file option
        save = input("\nSave results to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"./emails/{username}_emails.txt"
            with open(filename, 'w') as f:
                f.write(f"GitHub Email Extraction Results\n")
                f.write(f"Username: {username}\n")
                f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"\n{'='*60}\n\n")
                f.write(f"Emails found: {len(result['emails'])}\n\n")
                
                for email in result['emails']:
                    source = result['sources'].get(email, 'unknown')
                    f.write(f"{email} (from {source})\n")
                
                f.write(f"\n{'='*60}\n")
                f.write(f"API calls used: {result['api_calls_used']}\n")
            
            print(f"✓ Saved to: {filename}")
    else:
        print(f"\n✗ No emails found for {username}")
    
    # Extract another?
    print()
    another = input("Extract another user? (y/n): ").strip().lower()
    if another == 'y':
        print()
        main()


if __name__ == '__main__':
    main()

