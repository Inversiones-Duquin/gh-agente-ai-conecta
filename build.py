"""Build script v4 — empaqueta dependencias + Linux wheels para microVMs."""
import zipfile, os, shutil, tempfile, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, "dist")
SITE = os.path.join(BASE, ".venv", "Lib", "site-packages")
WHEELS_DIR = os.path.join(DIST, "linux_wheels")
os.makedirs(DIST, exist_ok=True)

# Next version
existing = [f for f in os.listdir(DIST) if f.startswith("agent-v") and f.endswith(".zip")]
nums = [int(f.replace("agent-v","").replace(".zip","")) for f in existing if f[7:-4].isdigit()]
version = max(nums) + 1 if nums else 234
out_path = os.path.join(DIST, f"agent-v{version}.zip")

ROOT_FILES = ["agent.py", "prompts.py", "helpers.py", "aws_clients.py", "requirements.txt"]

# Top-level dirs to skip entirely (truly not needed at runtime)
SKIP_TOP = {
    "pip", "setuptools", "wheel", "pkg_resources",
    "fpdf", "fpdf2", "xhtml2pdf", "reportlab", "Pillow",
    "fontTools", "lxml", "html5lib", "cssselect2", "tinycss2",
    "webencodings", "pypdf", "svglib", "arabic_reshaper", "python_bidi",
    "pyHanko", "pyhanko_certvalidator", "oscrypto", "asn1crypto",
    "uritools", "tzdata", "tzlocal",
    "bedrock_agentcore_starter_toolkit",
    "bedrock_agentcore_starter_toolkit-1.6.4.dist-info",
    "__pycache__",
}

# Packages with native extensions — skip Windows versions, use Linux wheels instead
NATIVE_PKGS = {"pydantic_core", "cryptography", "cffi", "rpds", "pycparser"}
NATIVE_DIRS = {
    "pydantic_core", "pydantic_core-2.46.3.dist-info",
    "cryptography", "cryptography-47.0.0.dist-info",
    "cffi", "cffi-2.0.0.dist-info",
    "rpds", "rpds_py-0.30.0.dist-info",
    "pycparser", "pycparser-3.0.dist-info",
}

SKIP_EXT = {".pyd", ".dll", ".exe", ".lib", ".pdb", ".pyc"}
SKIP_DIRS = {"__pycache__", ".git", "tests", "examples"}

# Step 0: Extract Linux wheels
print("Extracting Linux wheels...")
linux_pkgs_dir = os.path.join(DIST, "_linux_pkgs")
if os.path.isdir(linux_pkgs_dir):
    shutil.rmtree(linux_pkgs_dir)
os.makedirs(linux_pkgs_dir)

for whl in os.listdir(WHEELS_DIR):
    if whl.endswith(".whl"):
        whl_path = os.path.join(WHEELS_DIR, whl)
        with zipfile.ZipFile(whl_path, "r") as wz:
            wz.extractall(linux_pkgs_dir)
            print(f"  EXTRACTED: {whl}")

with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
    # 1. Root project files
    for fn in ROOT_FILES:
        fp = os.path.join(BASE, fn)
        if os.path.isfile(fp):
            zf.write(fp, fn)
            print(f"  + {fn}")

    # 2. mcps/ directory
    for root, dirs, files in os.walk(os.path.join(BASE, "mcps")):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if any(fn.endswith(ext) for ext in SKIP_EXT):
                continue
            fp = os.path.join(root, fn)
            arc = os.path.relpath(fp, BASE).replace("\\", "/")
            zf.write(fp, arc)
    print(f"  + mcps/")

    # 3. libs/ directory
    libs_dir = os.path.join(BASE, "libs")
    if os.path.isdir(libs_dir):
        for root, dirs, files in os.walk(libs_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.relpath(fp, BASE).replace("\\", "/")
                zf.write(fp, arc)
        print(f"  + libs/")

    # 4. Site-packages (skip native packages — Linux versions added below)
    count = 0
    for entry in sorted(os.listdir(SITE)):
        if entry in SKIP_TOP or entry in NATIVE_DIRS:
            continue
        pp = os.path.join(SITE, entry)
        if os.path.isdir(pp):
            for root, dirs, files in os.walk(pp):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    if any(fn.endswith(ext) for ext in SKIP_EXT):
                        continue
                    fp = os.path.join(root, fn)
                    arc = os.path.relpath(fp, SITE).replace("\\", "/")
                    zf.write(fp, arc)
                    count += 1
        elif os.path.isfile(pp):
            if any(entry.endswith(ext) for ext in SKIP_EXT):
                continue
            zf.write(pp, entry)
            count += 1
    print(f"  + {count} vendored files from site-packages")

    # 5. Linux wheel files (native extensions + Python code, overwrites .pyd with .so)
    linux_count = 0
    for root, dirs, files in os.walk(linux_pkgs_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if any(fn.endswith(ext) for ext in SKIP_EXT):
                continue
            fp = os.path.join(root, fn)
            arc = os.path.relpath(fp, linux_pkgs_dir).replace("\\", "/")
            zf.write(fp, arc)
            linux_count += 1
    print(f"  + {linux_count} files from Linux wheels")

# Cleanup
shutil.rmtree(linux_pkgs_dir)

mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"\n{out_path}: {mb:.1f} MB (v{version})")
