import subprocess
import json
import os
import time

# Configuration
ELASTRO_BIN = "elastro"  # Assumes in PATH or venv
INDEX_NAME = "e2e-test-index"
COMPONENT_NAME = "e2e-component"
TEMPLATE_NAME = "e2e-template"
DOC_FILE = "tests/e2e_doc.json"
BULK_FILE = "tests/e2e_bulk.json"
TEMPLATE_FILE = "tests/e2e_template.json"
COMPONENT_FILE = "tests/e2e_component.json"

def run_elastro(args):
    """Run elastro command and return output."""
    cmd = [ELASTRO_BIN] + args
    print(f"Running: {' '.join(cmd)}")
    try:
        # Use shell=False for safety, capture output
        # Assuming venv is activated in the shell running this script
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
    except Exception as e:
        print(f"Error running command: {e}")
        return None

def setup_files():
    """Create temporary test files."""
    with open(DOC_FILE, 'w') as f:
        json.dump({"name": "E2E Item", "price": 100, "category": "test"}, f)
    
    with open(BULK_FILE, 'w') as f:
        json.dump([
            {"name": "Bulk 1", "price": 10, "category": "test"},
            {"name": "Bulk 2", "price": 20, "category": "test"}
        ], f)
        
    with open(COMPONENT_FILE, 'w') as f:
        json.dump({
            "template": {
                "settings": {
                    "number_of_shards": 1
                },
                "mappings": {
                    "properties": {
                        "category": {"type": "keyword"}
                    }
                }
            }
        }, f)

    with open(TEMPLATE_FILE, 'w') as f:
        json.dump({
            "index_patterns": [f"{INDEX_NAME}*"],
            "composed_of": [COMPONENT_NAME],
            "template": {
                "mappings": {
                     "properties": {
                         "price": {"type": "integer"}
                     }
                }
            }
        }, f)

def cleanup_files():
    """Remove temp files."""
    for f in [DOC_FILE, BULK_FILE, TEMPLATE_FILE, COMPONENT_FILE]:
        if os.path.exists(f):
            os.remove(f)

def run_tests():
    print("🚀 Starting E2E CLI Tests...")
    setup_files()
    
    # 0. Cleanup from previous runs (ignore errors)
    run_elastro(["index", "delete", INDEX_NAME, "--force"])
    run_elastro(["template", "delete", TEMPLATE_NAME, "--type", "index", "--force"])
    run_elastro(["template", "delete", COMPONENT_NAME, "--type", "component", "--force"])

    # 1. Templates
    print("\n[1] Templates")
    # Create Component
    res = run_elastro(["template", "create", COMPONENT_NAME, "--type", "component", "--file", COMPONENT_FILE])
    if res.returncode != 0: print(f"❌ Failed to create component: {res.stderr}")
    else: print("✅ Component created")
    
    # Create Index Template
    res = run_elastro(["template", "create", TEMPLATE_NAME, "--type", "index", "--file", TEMPLATE_FILE])
    if res.returncode != 0: print(f"❌ Failed to create template: {res.stderr}")
    else: print("✅ Template created")

    # List & Verify
    res = run_elastro(["template", "list", "--type", "component"])
    if COMPONENT_NAME in res.stdout: print("✅ Component listed")
    else: print(f"❌ Component not found in list: {res.stdout}")

    # 2. Index
    print("\n[2] Index")
    res = run_elastro(["index", "create", INDEX_NAME])
    if res.returncode != 0: print(f"❌ Failed to create index: {res.stderr}")
    else: print("✅ Index created")

    # 3. Documents
    print("\n[3] Documents")
    # Single Index
    res = run_elastro(["doc", "index", INDEX_NAME, "--file", DOC_FILE, "--id", "1"])
    if res.returncode != 0: print(f"❌ Failed to index doc: {res.stderr}")
    else: print("✅ Document indexed")
    
    # Bulk Index
    res = run_elastro(["doc", "bulk", INDEX_NAME, "--file", BULK_FILE])
    if res.returncode != 0: print(f"❌ Failed bulk index: {res.stderr}")
    else: print("✅ Bulk index passed")
    
    # Refresh (using direct call since we don't have explicit refresh command yet? 
    # Wait, 'index open/close' exists, but force refresh? 
    # We rely on ES default refresh or wait)
    time.sleep(2) # Wait for refresh

    # 4. Search
    print("\n[4] Search")
    # Match All
    res = run_elastro(["doc", "search", INDEX_NAME])
    if "hits" in res.stdout: print("✅ Basic search passed")
    else: print(f"❌ Basic search failed: {res.stderr}")
    
    # Term Query (using new flags)
    res = run_elastro(["doc", "search", INDEX_NAME, "--term", "category=test"])
    if "hits" in res.stdout and '"total":' in res.stdout:
        # Check if we got hits (should be 3)
        print("✅ Term Search passed")
    else: print(f"❌ Term Search failed: {res.stdout}")

    # 5. Cleanup
    print("\n[5] Cleanup")
    run_elastro(["index", "delete", INDEX_NAME, "--force"])
    run_elastro(["template", "delete", TEMPLATE_NAME, "--type", "index", "--force"])
    run_elastro(["template", "delete", COMPONENT_NAME, "--type", "component", "--force"])
    
    cleanup_files()
    print("\n🎉 Tests Completed")

if __name__ == "__main__":
    run_tests()
