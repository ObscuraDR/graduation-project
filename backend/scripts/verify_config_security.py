"""
Security configuration verification script.
Run from the project root:  python backend/scripts/verify_config_security.py
"""

import os
import sys

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
DEFAULT_API_KEY = "changeme-set-API_KEY-in-env"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


def check(label: str, passed: bool, warn_only: bool = False) -> bool:
    tag = PASS if passed else (WARN if warn_only else FAIL)
    print(f"  [{tag}] {label}")
    return passed or warn_only


def main() -> None:
    # Load settings (triggers model_validator)
    try:
        from backend.config import Settings
        s = Settings()
    except RuntimeError as e:
        print(f"\n[{FAIL}] Settings validation failed:\n  {e}\n")
        sys.exit(1)

    env = s.environment.lower()
    is_prod = env == "production"
    failures = 0

    print(f"\n=== IDS Config Security Check  (ENVIRONMENT={env}) ===\n")

    # 1. ENVIRONMENT is explicitly set
    ok = env in ("development", "production")
    if not check("ENVIRONMENT is 'development' or 'production'", ok):
        failures += 1

    # 2. SECRET_KEY not default
    ok = s.secret_key != DEFAULT_SECRET_KEY
    if not check("SECRET_KEY is not the default value", ok, warn_only=not is_prod):
        failures += 1

    # 3. SECRET_KEY length
    ok = len(s.secret_key) >= 32
    if not check(f"SECRET_KEY length >= 32 (current: {len(s.secret_key)})", ok, warn_only=not is_prod):
        failures += 1

    # 4. API_KEY not default
    ok = s.api_key != DEFAULT_API_KEY
    if not check("API_KEY is not the default value", ok, warn_only=not is_prod):
        failures += 1

    # 5. API_KEY length
    ok = len(s.api_key) >= 16
    if not check(f"API_KEY length >= 16 (current: {len(s.api_key)})", ok, warn_only=not is_prod):
        failures += 1

    # 6. CORS — no wildcard
    origins = s.cors_origins
    ok = "*" not in origins
    if not check("CORS does not contain wildcard '*'", ok, warn_only=not is_prod):
        failures += 1

    # 7. CORS — non-empty in production
    ok = bool(origins)
    if not check(f"CORS_ORIGINS is set (current: {origins})", ok, warn_only=not is_prod):
        failures += 1

    # 8. Production-specific: CORS must not be localhost
    if is_prod:
        localhost_origins = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
        ok = not localhost_origins
        if not check(f"CORS has no localhost origins in production (found: {localhost_origins})", ok, warn_only=True):
            pass  # warn only

    print()
    if failures:
        print(f"  {failures} check(s) FAILED — fix before deploying to production.\n")
        sys.exit(1)
    else:
        print("  All checks passed.\n")


if __name__ == "__main__":
    main()
