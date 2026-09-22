"""Check that every manifest resource can reach a Git/CLI deployment."""
import ast
from pathlib import Path
import subprocess


root = Path(__file__).resolve().parents[1]
addon = root / "addons" / "thirdcode_accounting"
manifest = ast.literal_eval((addon / "__manifest__.py").read_text(encoding="utf-8"))
resources = [addon / name for name in manifest.get("data", [])]
for bundle in manifest.get("assets", {}).values():
    for pattern in bundle:
        if not isinstance(pattern, str):
            raise RuntimeError("Asset directives require explicit validation")
        matches = list((root / "addons").glob(pattern))
        if not matches:
            raise RuntimeError(f"Missing asset: {pattern}")
        resources.extend(matches)
for resource in resources:
    relative = resource.relative_to(root).as_posix()
    if not resource.is_file():
        raise RuntimeError(f"Missing package resource: {relative}")
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", relative], cwd=root,
        check=False,
    )
    if ignored.returncode != 1:
        raise RuntimeError(f"Ignored resource or git error: {relative}")
print(f"PASS: {len(resources)} accounting manifest resources are present and deployable")
