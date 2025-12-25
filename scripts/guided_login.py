#!/usr/bin/env python3
"""
Guided Browser Login Script

This script runs LOCALLY on your Mac (not in Docker) and opens a visible browser
window for you to log into Twitter or Instagram. Once you complete the login,
it automatically captures your session cookies and sends them to the backend API.

Requirements:
    pip install playwright httpx
    playwright install chromium

Usage:
    python scripts/guided_login.py --platform twitter --persona-id <uuid>
    python scripts/guided_login.py --platform instagram --persona-id <uuid>

    # List all personas:
    python scripts/guided_login.py --list-personas

    # Specify custom API URL:
    python scripts/guided_login.py --platform twitter --persona-id <uuid> --api-url http://localhost:8000
"""

import argparse
import asyncio
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


# Default API URL (Docker backend)
DEFAULT_API_URL = "http://localhost:8000"


async def list_personas(api_url: str) -> None:
    """List all personas from the API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{api_url}/api/personas")
            response.raise_for_status()
            personas = response.json()
            
            if not personas:
                print("No personas found.")
                return
            
            print("\n📋 Available Personas:\n")
            print("-" * 70)
            for p in personas:
                accounts = []
                # Get platform accounts for this persona
                try:
                    acc_resp = await client.get(f"{api_url}/api/personas/{p['id']}/accounts")
                    if acc_resp.status_code == 200:
                        for acc in acc_resp.json():
                            status = "✅" if acc.get("engagement_enabled") else "⚠️"
                            accounts.append(f"{acc['platform']} {status}")
                except:
                    pass
                
                accounts_str = ", ".join(accounts) if accounts else "No accounts"
                print(f"  {p['name']}")
                print(f"    ID: {p['id']}")
                print(f"    Accounts: {accounts_str}")
                print()
            
        except httpx.HTTPError as e:
            print(f"Error connecting to API: {e}")
            print(f"Make sure the backend is running at {api_url}")
            sys.exit(1)


async def guided_login_twitter(persona_id: str, api_url: str) -> bool:
    """Open browser for Twitter login and capture cookies."""
    print("\n🐦 Twitter Guided Login")
    print("=" * 50)
    print("A browser window will open. Please log into Twitter/X.")
    print("Once you're logged in, the window will close automatically.\n")
    
    playwright = None
    browser = None
    
    try:
        playwright = await async_playwright().start()
        
        # Launch VISIBLE browser
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # Navigate to Twitter login
        print("📱 Opening Twitter login page...")
        await page.goto("https://twitter.com/i/flow/login", wait_until="domcontentloaded")
        
        print("⏳ Waiting for you to complete login (up to 5 minutes)...")
        print("   Handle any 2FA or security challenges as needed.\n")
        
        # Wait for login completion
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 2
        logged_in = False
        
        for i in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            # Check if we're on home page
            if "twitter.com/home" in current_url or "x.com/home" in current_url:
                # Check for essential cookies
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies if "twitter.com" in c.get("domain", "") or "x.com" in c.get("domain", "")}
                
                if "auth_token" in cookie_dict and "ct0" in cookie_dict:
                    logged_in = True
                    print("✅ Login detected! Capturing cookies...\n")
                    break
            
            # Show progress every 10 seconds
            if i > 0 and i % 5 == 0:
                elapsed = i * poll_interval
                print(f"   Still waiting... ({elapsed}s elapsed)")
        
        if not logged_in:
            print("❌ Login timeout. Please try again.")
            return False
        
        # Capture cookies
        all_cookies = await context.cookies()
        twitter_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if "twitter.com" in c.get("domain", "") or "x.com" in c.get("domain", "")
        }
        
        if not twitter_cookies:
            print("❌ No cookies captured. Please try again.")
            return False
        
        print(f"📦 Captured {len(twitter_cookies)} cookies")
        
        # Send to API
        print(f"📤 Sending cookies to API...")
        
        # Format cookies as the API expects
        cookie_str = "; ".join([f"{k}={v}" for k, v in twitter_cookies.items()])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/personas/{persona_id}/accounts/twitter/set-cookies",
                json={"cookies": cookie_str},
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("\n✅ Success! Twitter engagement is now enabled.")
                    print(f"   {result.get('message', '')}")
                    return True
                else:
                    print(f"\n❌ API error: {result.get('message', 'Unknown error')}")
                    return False
            else:
                print(f"\n❌ API request failed: {response.status_code}")
                print(f"   {response.text}")
                return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def guided_login_instagram(persona_id: str, api_url: str) -> bool:
    """Open browser for Instagram login and capture cookies."""
    print("\n📸 Instagram Guided Login")
    print("=" * 50)
    print("A browser window will open. Please log into Instagram.")
    print("Once you're logged in, the window will close automatically.\n")
    
    playwright = None
    browser = None
    
    try:
        playwright = await async_playwright().start()
        
        # Launch VISIBLE browser
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # Navigate to Instagram login
        print("📱 Opening Instagram login page...")
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        
        print("⏳ Waiting for you to complete login (up to 5 minutes)...")
        print("   Handle any 2FA or security challenges as needed.\n")
        
        # Wait for login completion
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 2
        logged_in = False
        username = None
        
        for i in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            # Check if we're past the login page
            if "instagram.com" in current_url and "/accounts/login" not in current_url:
                # Check for essential cookies
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies if "instagram.com" in c.get("domain", "")}
                
                if "sessionid" in cookie_dict or "ds_user_id" in cookie_dict:
                    logged_in = True
                    print("✅ Login detected! Capturing cookies...\n")
                    
                    # Try to extract username from URL if on profile
                    if "/accounts/" not in current_url and "instagram.com/" in current_url:
                        parts = current_url.replace("https://", "").replace("www.", "").split("/")
                        if len(parts) >= 2 and parts[1] and parts[1] not in ["explore", "direct", "reels", "stories"]:
                            username = parts[1]
                    break
            
            # Show progress every 10 seconds
            if i > 0 and i % 5 == 0:
                elapsed = i * poll_interval
                print(f"   Still waiting... ({elapsed}s elapsed)")
        
        if not logged_in:
            print("❌ Login timeout. Please try again.")
            return False
        
        # Capture cookies
        all_cookies = await context.cookies()
        instagram_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if "instagram.com" in c.get("domain", "")
        }
        
        if not instagram_cookies:
            print("❌ No cookies captured. Please try again.")
            return False
        
        print(f"📦 Captured {len(instagram_cookies)} cookies")
        if username:
            print(f"👤 Detected username: {username}")
        
        # Send to API - Instagram uses the same cookie format
        print(f"📤 Sending cookies to API...")
        
        # Format cookies as the API expects
        cookie_str = "; ".join([f"{k}={v}" for k, v in instagram_cookies.items()])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/personas/{persona_id}/accounts/instagram/set-cookies",
                json={"cookies": cookie_str},
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("\n✅ Success! Instagram session is now enabled.")
                    print(f"   {result.get('message', '')}")
                    return True
                else:
                    print(f"\n❌ API error: {result.get('message', 'Unknown error')}")
                    return False
            elif response.status_code == 404:
                # Instagram account might not exist, try to create via different endpoint
                print("   Instagram account not found, cookies captured but not saved.")
                print("   You may need to connect Instagram first via the dashboard.")
                return False
            else:
                print(f"\n❌ API request failed: {response.status_code}")
                print(f"   {response.text}")
                return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def main():
    parser = argparse.ArgumentParser(
        description="Guided Browser Login - Capture session cookies for Twitter/Instagram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all personas
    python scripts/guided_login.py --list-personas
    
    # Twitter login for a persona
    python scripts/guided_login.py --platform twitter --persona-id abc-123-def
    
    # Instagram login
    python scripts/guided_login.py --platform instagram --persona-id abc-123-def
        """,
    )
    
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="List all personas and their connection status",
    )
    parser.add_argument(
        "--platform",
        choices=["twitter", "instagram"],
        help="Platform to log into",
    )
    parser.add_argument(
        "--persona-id",
        help="UUID of the persona to save cookies for",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Backend API URL (default: {DEFAULT_API_URL})",
    )
    
    args = parser.parse_args()
    
    print("\n🔐 Guided Browser Login")
    print("=" * 50)
    print(f"API URL: {args.api_url}\n")
    
    if args.list_personas:
        await list_personas(args.api_url)
        return
    
    if not args.platform:
        parser.error("--platform is required (use --list-personas to see available personas)")
    
    if not args.persona_id:
        parser.error("--persona-id is required (use --list-personas to see available personas)")
    
    # Run the appropriate login flow
    if args.platform == "twitter":
        success = await guided_login_twitter(args.persona_id, args.api_url)
    else:
        success = await guided_login_instagram(args.persona_id, args.api_url)
    
    if success:
        print("\n🎉 All done! You can close this terminal.")
    else:
        print("\n⚠️  Login was not completed. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

