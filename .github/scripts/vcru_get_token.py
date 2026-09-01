#!/usr/bin/env python3
"""Capture vc.ru JWT from browser CDP session."""
import time, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9221")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    try:
        # Navigate to vc.ru editor to trigger autosave
        page.goto("https://vc.ru/new", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        
        # Check if logged in
        url = page.url
        print("URL:", url)
        
        if "signin" in url or "login" in url:
            print("NOT_LOGGED_IN")
        else:
            # Try to intercept JWT from page cookies or localStorage
            jwt = page.evaluate("""
                (() => {
                    // Check localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key.includes('jwt') || key.includes('token') || key.includes('auth')) {
                            return key + '=' + localStorage.getItem(key);
                        }
                    }
                    return null;
                })()
            """)
            print("JWT from localStorage:", jwt)
            
            # Also check cookies
            cookies = ctx.cookies("https://vc.ru")
            for c in cookies:
                if 'jwt' in c['name'].lower() or 'token' in c['name'].lower() or 'auth' in c['name'].lower():
                    print(f"Cookie: {c['name']}={c['value'][:50]}...")
    finally:
        page.close()
        browser.close()