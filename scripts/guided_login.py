#!/usr/bin/env python3
"""
Guided Browser Login Script

This script runs LOCALLY on your Mac (not in Docker) and opens a visible browser
window for you to log into Twitter, Instagram, Fanvue, or Higgsfield. Once you 
complete the login, it automatically captures your session cookies and sends them 
to the backend API.

Requirements:
    pip install playwright httpx
    playwright install chromium

Usage:
    python scripts/guided_login.py --platform twitter --persona-id <uuid>
    python scripts/guided_login.py --platform instagram --persona-id <uuid>
    python scripts/guided_login.py --platform fanvue --persona-id <uuid>
    python scripts/guided_login.py --platform higgsfield --persona-id <uuid>

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


async def guided_login_fanvue(persona_id: str, api_url: str) -> bool:
    """Open browser for Fanvue login and capture cookies."""
    print("\n💖 Fanvue Guided Login")
    print("=" * 50)
    print("A browser window will open. Please log into Fanvue.")
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
        
        # Navigate to Fanvue login
        print("📱 Opening Fanvue sign-in page...")
        await page.goto("https://www.fanvue.com/signin", wait_until="domcontentloaded")
        
        print("⏳ Waiting for you to complete login (up to 5 minutes)...")
        print("   Handle any 2FA or security challenges as needed.\n")
        
        # Wait for login completion
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 2
        logged_in = False
        
        for i in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            # Check if we're past the login page (on home, feed, or dashboard)
            if "fanvue.com" in current_url and "/signin" not in current_url:
                # Check for session cookies (Fanvue uses various session identifiers)
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies if "fanvue.com" in c.get("domain", "")}
                
                # Look for session-related cookies
                has_session = any(
                    name in cookie_dict or "session" in name.lower() or "auth" in name.lower()
                    for name in cookie_dict.keys()
                )
                
                if has_session or len(cookie_dict) >= 3:
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
        fanvue_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if "fanvue.com" in c.get("domain", "")
        }
        
        if not fanvue_cookies:
            print("❌ No cookies captured. Please try again.")
            return False
        
        print(f"📦 Captured {len(fanvue_cookies)} cookies")
        
        # Send to API
        print(f"📤 Sending cookies to API...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/personas/{persona_id}/accounts/fanvue/cookies",
                json={"cookies": fanvue_cookies},  # Fanvue expects dict format
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("\n✅ Success! Fanvue is now connected.")
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


async def guided_login_higgsfield(persona_id: str, api_url: str) -> bool:
    """Open browser for Higgsfield login and capture cookies.
    
    Higgsfield cookies are used for NSFW image generation via browser automation,
    bypassing API-level content moderation.
    """
    print("\n🎨 Higgsfield Guided Login")
    print("=" * 50)
    print("A browser window will open. Please log into Higgsfield.")
    print("Once you're logged in, the window will close automatically.")
    print("\nNote: This is used for NSFW image generation via browser automation.\n")
    
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
        
        # Navigate to Higgsfield - check if there's a login/sign in link
        print("📱 Opening Higgsfield page...")
        await page.goto("https://higgsfield.ai", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Check if already logged in by looking for Sign In button
        sign_in_button = page.locator('a:has-text("Sign In"), button:has-text("Sign In"), a:has-text("Login"), button:has-text("Login")')
        if await sign_in_button.count() > 0:
            print("   Found Sign In button - clicking to login...")
            # Use no_wait_after to avoid waiting for navigation to complete
            # This prevents timeout when Google OAuth redirects happen
            try:
                await sign_in_button.first.click(no_wait_after=True, timeout=5000)
            except Exception as click_err:
                # Click may "fail" due to navigation, but that's expected
                print(f"   Sign In click initiated (navigation in progress...)")
            await asyncio.sleep(3)  # Give time for OAuth redirect to start
        
        print("⏳ Waiting for you to complete login (up to 5 minutes)...")
        print("   Please log in using your Higgsfield account.\n")
        
        # Wait for login completion
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 3
        logged_in = False
        initial_check_done = False
        
        for i in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            try:
                # First, check if Sign In button is GONE (indicates logged in)
                sign_in_still_visible = await page.locator('a:has-text("Sign In"), button:has-text("Sign In")').count() > 0
                
                # Look for definitive logged-in indicators (user profile elements)
                logged_in_indicators = [
                    # User menu / profile indicators
                    'button:has-text("Sign Out")',
                    'a:has-text("Sign Out")',
                    'button:has-text("Log Out")',
                    'a:has-text("Log Out")',
                    '[data-testid="user-menu"]',
                    '[data-testid="user-avatar"]',
                    # Profile link that includes actual username
                    'a[href*="/profile"]',
                    # Credits/usage indicators (only visible when logged in)
                    ':text("credits")',
                    ':text("Credits")',
                ]
                
                for selector in logged_in_indicators:
                    try:
                        count = await page.locator(selector).count()
                        if count > 0:
                            logged_in = True
                            break
                    except:
                        continue
                
                # Alternative: Sign In button disappeared AND we have auth cookies
                if not sign_in_still_visible and not logged_in:
                    cookies = await context.cookies()
                    # Look for auth-related cookies
                    auth_cookies = [
                        c for c in cookies 
                        if "higgsfield" in c.get("domain", "") and 
                        any(x in c.get("name", "").lower() for x in ["session", "auth", "token", "user", "id"])
                    ]
                    if len(auth_cookies) >= 1:
                        # Additional check: make sure we're not on a login page
                        if "login" not in current_url.lower() and "signin" not in current_url.lower():
                            logged_in = True
                
                if logged_in:
                    print("✅ Login detected! Capturing cookies...\n")
                    break
                    
            except Exception as e:
                # Ignore errors during checking
                pass
            
            # Show progress every 15 seconds
            if i > 0 and i % 5 == 0:
                elapsed = i * poll_interval
                print(f"   Still waiting... ({elapsed}s elapsed)")
        
        if not logged_in:
            print("❌ Login timeout. Please try again.")
            return False
        
        # Capture all cookies (Higgsfield uses various domains)
        all_cookies = await context.cookies()
        
        # Filter for Higgsfield-related cookies
        higgsfield_cookies = [
            c for c in all_cookies
            if "higgsfield" in c.get("domain", "")
        ]
        
        # If no specific higgsfield cookies, capture all (some may be on subdomains)
        if not higgsfield_cookies:
            higgsfield_cookies = all_cookies
        
        if not higgsfield_cookies:
            print("❌ No cookies captured. Please try again.")
            return False
        
        print(f"📦 Captured {len(higgsfield_cookies)} cookies")
        
        # Send to API
        print(f"📤 Sending cookies to API...")
        
        import json
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/personas/{persona_id}/higgsfield/cookies",
                json={"cookies": higgsfield_cookies},  # Send as list of cookie objects
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("\n✅ Success! Higgsfield browser automation is now enabled.")
                    print(f"   {result.get('message', '')}")
                    print("\n   NSFW image generation will now use browser automation")
                    print("   to bypass API content moderation.")
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


async def main():
    parser = argparse.ArgumentParser(
        description="Guided Browser Login - Capture session cookies for Twitter/Instagram/Fanvue/Higgsfield",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all personas
    python scripts/guided_login.py --list-personas
    
    # Twitter login for a persona
    python scripts/guided_login.py --platform twitter --persona-id abc-123-def
    
    # Instagram login
    python scripts/guided_login.py --platform instagram --persona-id abc-123-def
    
    # Fanvue login
    python scripts/guided_login.py --platform fanvue --persona-id abc-123-def
    
    # Higgsfield login (for NSFW image generation)
    python scripts/guided_login.py --platform higgsfield --persona-id abc-123-def
        """,
    )
    
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="List all personas and their connection status",
    )
    parser.add_argument(
        "--platform",
        choices=["twitter", "instagram", "fanvue", "higgsfield"],
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
    elif args.platform == "instagram":
        success = await guided_login_instagram(args.persona_id, args.api_url)
    elif args.platform == "higgsfield":
        success = await guided_login_higgsfield(args.persona_id, args.api_url)
    else:
        success = await guided_login_fanvue(args.persona_id, args.api_url)
    
    if success:
        print("\n🎉 All done! You can close this terminal.")
    else:
        print("\n⚠️  Login was not completed. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

