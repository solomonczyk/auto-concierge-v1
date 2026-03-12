"""
One-time script: replace client+login with client_auth in test files.
Run from backend/: python scripts/update_tests_for_csrf.py
"""
import re
from pathlib import Path

LOGIN_BLOCK = re.compile(
    r'\n    await client\.post\(\s*\n'
    r'        f"\{settings\.API_V1_STR\}/login/access-token",\s*\n'
    r'        data=\{"username": "admin", "password": "admin"\},\s*\n'
    r'        headers=\{"content-type": "application/x-www-form-urlencoded"\},\s*\n'
    r'    \)\s*\n',
    re.MULTILINE
)

LOGIN_BLOCK_ALT = re.compile(
    r'\n        await client\.post\(\s*\n'
    r'            f"\{settings\.API_V1_STR\}/login/access-token",\s*\n'
    r'            data=\{"username": "admin", "password": "admin"\},\s*\n'
    r'            headers=\{"content-type": "application/x-www-form-urlencoded"\},\s*\n'
    r'        \)\s*\n',
    re.MULTILINE
)

def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    # Replace client: AsyncClient with client_auth: AsyncClient when followed by login
    if "login/access-token" not in text:
        return False
    # Remove 4-line login blocks (various indentations)
    text = LOGIN_BLOCK.sub("\n", text)
    text = LOGIN_BLOCK_ALT.sub("\n", text)
    # Replace (client: AsyncClient) with (client_auth: AsyncClient) when test has mutating
    # Only in tests that had login (we removed it)
    if "client: AsyncClient" in text and "client_auth" not in text:
        # Replace first occurrence in each function that had login
        text = text.replace("(client: AsyncClient)", "(client_auth: AsyncClient)")
        text = text.replace("(client: AsyncClient,", "(client_auth: AsyncClient,")
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False

def main():
    tests_dir = Path(__file__).parent.parent / "tests"
    updated = []
    for f in tests_dir.rglob("*.py"):
        if "conftest" in f.name or "test_csrf" in f.name:
            continue
        if process_file(f):
            updated.append(str(f))
    for u in updated:
        print(f"Updated: {u}")

if __name__ == "__main__":
    main()
