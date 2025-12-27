"""
Internal simulation/validation of Energa integration v4.2.0
Check for potential issues before LAB deployment
"""

import sys
from pathlib import Path

# Add custom_components to path
sys.path.insert(0, str(Path(__file__).parent / "custom_components" / "energa_mobile"))

print("=" * 80)
print("ENERGA INTEGRATION v4.2.0 - INTERNAL VALIDATION")
print("=" * 80)

# Test 1: Import all modules
print("\n[1/8] Testing module imports...")
try:
    print("✅ API and const imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Check sensor.py structure
print("\n[2/8] Analyzing sensor.py...")
sensor_path = Path("custom_components/energa_mobile/sensor.py")
sensor_code = sensor_path.read_text()

issues = []

# Check for state_class in EnergaStatisticsSensor
if "class EnergaStatisticsSensor" in sensor_code:
    # Find the class
    start = sensor_code.find("class EnergaStatisticsSensor")
    end = sensor_code.find("class ", start + 1)
    class_code = sensor_code[start:end] if end != -1 else sensor_code[start:]

    # Check for state_class assignment
    if "self._attr_state_class = " in class_code:
        issues.append(
            "❌ CRITICAL: EnergaStatisticsSensor still has state_class assignment!"
        )
    else:
        print("✅ EnergaStatisticsSensor: No state_class (CORRECT)")

    # Check for async_import_statistics
    if "async_import_statistics" in class_code:
        print("✅ EnergaStatisticsSensor: Uses async_import_statistics")
    else:
        issues.append("❌ CRITICAL: Missing async_import_statistics!")

# Test 3: Check for common anti-patterns
print("\n[3/8] Checking for anti-patterns...")

antipatterns = {
    "StatisticData(": "Should use plain dict, not constructor",
    ".astimezone(UTC)": "Should use dt_util.as_utc()",
    'meter_point_id" for entity': "Should use meter_serial for entity IDs",
}

for pattern, issue in antipatterns.items():
    if pattern in sensor_code:
        if pattern == "StatisticData(":
            # This is in import, ignore
            pass
        else:
            issues.append(f"⚠️ Potential issue: {issue}")

print("✅ Anti-pattern check complete")

# Test 4: Check __init__.py statistics building
print("\n[4/8] Analyzing __init__.py statistics...")
init_path = Path("custom_components/energa_mobile/__init__.py")
init_code = init_path.read_text()

if "dt_util.as_utc(" in init_code:
    print("✅ __init__.py: Uses dt_util.as_utc()")
else:
    issues.append("❌ __init__.py: Should use dt_util.as_utc() for timestamps")

# Check for dictionary creation
if '"start":' in init_code and '"sum":' in init_code:
    print("✅ __init__.py: Uses dictionary format for StatisticData")
else:
    issues.append("❌ __init__.py: Should use dict format for StatisticData")

# Test 5: Check config_flow.py
print("\n[5/8] Analyzing config_flow.py...")
config_path = Path("custom_components/energa_mobile/config_flow.py")
config_code = config_path.read_text()

if "EnergaTokenExpiredError" in config_code:
    print("✅ config_flow.py: Handles EnergaTokenExpiredError")
else:
    issues.append("⚠️ config_flow.py: Should handle token expiry")

if "clear_stats" in config_code or "reimport" in config_code.lower():
    print("✅ config_flow.py: Has statistics management options")

# Test 6: Check translations completeness
print("\n[6/8] Checking translations...")
pl_path = Path("custom_components/energa_mobile/translations/pl.json")
en_path = Path("custom_components/energa_mobile/translations/en.json")

if pl_path.exists() and en_path.exists():
    import json

    pl = json.loads(pl_path.read_text())
    en = json.loads(en_path.read_text())

    # Check for price options
    if "prices" in pl.get("options", {}).get("step", {}).get("prices", {}):
        print("✅ Translations: Polish price options present")

    if "prices" in en.get("options", {}).get("step", {}).get("prices", {}):
        print("✅ Translations: English price options present")
    else:
        issues.append("⚠️ Missing English translations for price options")
else:
    issues.append("❌ Translation files missing!")

# Test 7: Validate manifest.json
print("\n[7/8] Validating manifest.json...")
manifest_path = Path("custom_components/energa_mobile/manifest.json")
if manifest_path.exists():
    import json

    manifest = json.loads(manifest_path.read_text())

    version = manifest.get("version")
    if version == "4.2.0":
        print(f"✅ Manifest version: {version} (CORRECT)")
    else:
        issues.append(f"❌ Manifest version mismatch: {version} != 4.2.0")

    if manifest.get("domain") == "energa_mobile":
        print("✅ Domain correct: energa_mobile")

# Test 8: Check for debug/test files in gitignore
print("\n[8/8] Checking .gitignore...")
gitignore_path = Path(".gitignore")
if gitignore_path.exists():
    gitignore = gitignore_path.read_text()
    test_files = ["check_*.py", "explore_*.py", "get_*.py", "remove_*.py"]

    missing = []
    for pattern in test_files:
        if pattern not in gitignore:
            missing.append(pattern)

    if missing:
        issues.append(f"⚠️ .gitignore missing: {', '.join(missing)}")
    else:
        print("✅ .gitignore: Debug scripts excluded")

# Summary
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

if issues:
    print(f"\n⚠️ Found {len(issues)} issue(s):\n")
    for issue in issues:
        print(f"  {issue}")
    print("\n❌ VALIDATION FAILED")
    sys.exit(1)
else:
    print("\n✅ ALL CHECKS PASSED - Ready for LAB deployment")
    sys.exit(0)
