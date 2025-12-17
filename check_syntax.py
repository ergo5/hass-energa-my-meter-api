import ast
import sys
import os

file_path = r"c:\Users\dciesiel\OneDrive - Adtran\Documents\GitHub\hass-energa-my-meter-api\hass-energa-my-meter-api\custom_components\energa_mobile\__init__.py"

print(f"Checking syntax for: {file_path}")

try:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    
    # Attempt to parse the code into an AST
    tree = ast.parse(source)
    print("✅ SYNTAX CHECK PASSED: The file is valid Python code.")
    print("✅ No IndentationError or SyntaxError found.")
    
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR DETECTED: {e}")
    print(f"Line {e.lineno}, Offset {e.offset}: {e.text}")
    sys.exit(1)
except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")
    sys.exit(1)
