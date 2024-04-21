import os
from typing import Any, Dict, List

import toml


def convert_version(version: str) -> str:
    if version.startswith("^"):
        return version[1:]
    return version


def extract_dependencies(pyproject_toml: Dict[str, Any]) -> List[str]:
    dependencies = (
        pyproject_toml.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    extracted: list[str] = []
    for dependency, version in dependencies.items():
        if dependency == "python":
            continue

        extracted.append(f"{dependency}>={convert_version(version)}")

    return extracted


def main():
    current_dir = os.getcwd()
    pyproject_path = os.path.join(current_dir, "pyproject.toml")
    requirements_path = os.path.join(current_dir, "requirements.txt")

    with open(pyproject_path, "r") as file:
        pyproject_toml = toml.load(file)

    dependencies = extract_dependencies(pyproject_toml)

    with open(requirements_path, "w") as file:
        file.write("\n".join(dependencies))

    print("Requirements file created successfully.")


if __name__ == "__main__":
    main()
