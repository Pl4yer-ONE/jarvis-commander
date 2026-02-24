#!/usr/bin/env python3
"""
Max — WiFi Captive Portal Auto-Login

Automatically detects and logs into the Providence_Faculty captive portal.
Runs in a loop checking connectivity and re-authenticating as needed.
"""

import logging
import subprocess
import time
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [wifi-login] %(message)s")
logger = logging.getLogger("wifi-login")

# Captive portal credentials
PORTAL_USER = "mathews"
PORTAL_PASS = "mathews.1"

# Common captive portal detection URLs
CHECK_URLS = [
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://clients3.google.com/generate_204",
    "http://www.google.com/generate_204",
]

# Common captive portal login page patterns
PORTAL_URLS = [
    "http://192.168.1.1",
    "http://10.0.0.1",
    "http://1.1.1.1",
    "http://captive.apple.com",
    "http://neverssl.com",
]


def is_connected():
    """Check if we have real internet access (not captive portal)."""
    for url in CHECK_URLS:
        try:
            r = requests.get(url, timeout=5, allow_redirects=False)
            if r.status_code == 204:
                return True
        except Exception:
            continue
    return False


def get_redirect_url():
    """Detect captive portal by following redirects."""
    try:
        r = requests.get("http://connectivitycheck.gstatic.com/generate_204",
                         timeout=10, allow_redirects=True)
        if r.status_code != 204 and r.url != "http://connectivitycheck.gstatic.com/generate_204":
            logger.info("Captive portal detected at: %s", r.url)
            return r.url
    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        logger.debug("Redirect check error: %s", e)
    return None


def attempt_portal_login(portal_url):
    """Try to authenticate with the captive portal."""
    session = requests.Session()

    try:
        # Step 1: Load the portal login page
        logger.info("Loading portal page: %s", portal_url)
        r = session.get(portal_url, timeout=10)

        if r.status_code != 200:
            logger.warning("Portal page returned %d", r.status_code)
            return False

        page = r.text.lower()
        login_url = r.url  # May have redirected

        # Step 2: Try common form submission patterns
        # Pattern 1: username/password form
        form_data_variants = [
            {"username": PORTAL_USER, "password": PORTAL_PASS},
            {"user": PORTAL_USER, "pass": PORTAL_PASS},
            {"admin": PORTAL_USER, "pwd": PORTAL_PASS},
            {"login": PORTAL_USER, "password": PORTAL_PASS},
            {"userId": PORTAL_USER, "password": PORTAL_PASS},
            {"email": PORTAL_USER, "password": PORTAL_PASS},
        ]

        for form_data in form_data_variants:
            try:
                r = session.post(login_url, data=form_data, timeout=10,
                                 allow_redirects=True)
                logger.info("POST %s -> %d (tried: %s)", login_url,
                            r.status_code, list(form_data.keys()))

                # Check if we now have internet
                time.sleep(2)
                if is_connected():
                    logger.info("✅ Portal login successful!")
                    return True
            except Exception as e:
                logger.debug("Form submit error: %s", e)

        # Pattern 2: Try URL-encoded login at common endpoints
        login_endpoints = [
            login_url.rstrip("/") + "/login",
            login_url.rstrip("/") + "/auth",
            login_url.rstrip("/") + "/authenticate",
        ]

        for endpoint in login_endpoints:
            for form_data in form_data_variants[:2]:
                try:
                    r = session.post(endpoint, data=form_data, timeout=10)
                    time.sleep(2)
                    if is_connected():
                        logger.info("✅ Portal login successful via %s!", endpoint)
                        return True
                except Exception:
                    continue

    except Exception as e:
        logger.error("Portal login attempt failed: %s", e)

    return False


def ensure_wifi_connected():
    """
    Ensure WiFi is connected to *some* known network.
    NM handles priority automatically (Airtel_Air Fiber=100 > Providence=50).
    Returns True if connected to Providence_Faculty (needs auth check),
    False if connected to another trusted network or disconnected.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
            capture_output=True, text=True, timeout=10
        )
        active = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        
        if "Providence_Faculty" in active:
            return True, "Providence_Faculty"
        elif "Airtel_Air Fiber" in active or "oneplus" in active:
            return False, active[0]

        # No known active network. Let NM auto-connect, but also explicitly try highest priority
        logger.info("No known active connection. Triggering auto-connect...")
        subprocess.run(["nmcli", "device", "wifi", "connect", "Airtel_Air Fiber"], capture_output=True, timeout=10)
        time.sleep(3)
        return False, None
    except Exception as e:
        logger.debug("WiFi connect error: %s", e)
        return False, None


def main():
    logger.info("🌐 WiFi auto-login daemon started")
    logger.info("   Priorities: Airtel_Air Fiber > Providence_Faculty > oneplus")

    consecutive_ok = 0
    last_network = None

    while True:
        try:
            # Step 1: Check active connection
            needs_portal_check, active_net = ensure_wifi_connected()
            
            if active_net and active_net != last_network:
                logger.info("📡 Connected to: %s", active_net)
                last_network = active_net

            if not needs_portal_check:
                if active_net:
                    time.sleep(30)  # We're on a trusted network (e.g. Airtel), just wait
                else:
                    time.sleep(15)  # Trying to connect
                continue

            # Step 2: Check if we have real internet
            if is_connected():
                if consecutive_ok == 0:
                    logger.info("✅ Internet is working")
                consecutive_ok += 1
                time.sleep(60)  # Check every 60s when connected
                continue

            consecutive_ok = 0
            logger.info("⚠️ No internet — checking for captive portal...")

            # Step 3: Detect and login to captive portal
            portal_url = get_redirect_url()
            if portal_url:
                attempt_portal_login(portal_url)
            else:
                # Try common portal URLs directly
                for url in PORTAL_URLS:
                    try:
                        r = requests.get(url, timeout=5)
                        if r.status_code == 200 and len(r.text) > 100:
                            if attempt_portal_login(url):
                                break
                    except Exception:
                        continue

            time.sleep(15)  # Wait before next check

        except Exception as e:
            logger.error("Loop error: %s", e)
            time.sleep(30)


if __name__ == "__main__":
    main()
