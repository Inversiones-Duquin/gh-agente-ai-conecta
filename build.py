"""Build script — empaqueta el agente usando agent-v17.zip (Linux) como base."""
import zipfile, os

DIST = "dist"
BASE_ZIP = "agent-v13.zip"  # zip base (v55) — ultimo 100% funcional en Linux
SITE = ".venv/Lib/site-packages"

# Archivos raiz actualizados
ROOT_UPDATED = ["agent.py", "prompts.py", "requirements.txt"]

# Paquetes adicionales a vendear
EXTRA_PACKAGES = {
    # xhtml2pdf + ReportLab stack
    "xhtml2pdf": "xhtml2pdf", "reportlab": "reportlab",
    "html5lib": "html5lib", "cssselect2": "cssselect2",
    "tinycss2": "tinycss2", "webencodings": "webencodings",
    "lxml": "lxml", "pypdf": "pypdf",
    "svglib": "svglib", "arabic_reshaper": "arabic_reshaper",
    "python_bidi": "python_bidi", "pyHanko": "pyHanko",
    "pyhanko_certvalidator": "pyhanko_certvalidator",
    "oscrypto": "oscrypto", "asn1crypto": "asn1crypto",
    "uritools": "uritools", "tzdata": "tzdata", "tzlocal": "tzlocal",
    # fpdf2 + fonttools (mantener como fallback)
    "fpdf": "fpdf", "fontTools": "fontTools",
}

os.makedirs(DIST, exist_ok=True)

# Version auto-incremental
existing = [f for f in os.listdir(DIST) if f.startswith("agent-v") and f.endswith(".zip")]
nums = [int(f.replace("agent-v","").replace(".zip","")) for f in existing if f[8:-4].isdigit()]
version = max(nums) + 1 if nums else 24
out_path = os.path.join(DIST, f"agent-v{version}.zip")

with zipfile.ZipFile(BASE_ZIP, "r") as zin:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn = item.filename
            # Saltar paths viejos
            if fn.startswith("mcp/"):
                continue
            if fn.startswith("mcps/"):
                continue
            if fn.startswith("reports/"):
                continue
            if fn.startswith("openapi-specs/"):
                continue
            # Actualizar archivos fuente modificados
            if fn in ROOT_UPDATED:
                zout.write(fn, fn)
                print(f"  U: {fn}")
            else:
                data = zin.read(fn)
                zout.writestr(item, data)

        # mcps/ completo (i2dw + reports + openapi specs)
        for root, dirs, files in os.walk("mcps"):
            for fn in files:
                if "__pycache__" in root or fn.endswith(".pyc"):
                    continue
                full = os.path.join(root, fn)
                zout.write(full, full.replace("\\", "/"))
        print(f"  N: mcps/ (i2dw + reports + specs)")

        # Paquetes extra
        for src_dir, arc_base in EXTRA_PACKAGES.items():
            pkg_path = os.path.join(SITE, src_dir)
            if os.path.isdir(pkg_path):
                for root, dirs, files in os.walk(pkg_path):
                    for fn in files:
                        if "__pycache__" in root:
                            continue
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, SITE).replace("\\", "/")
                        zout.write(full, rel)
        print(f"  N: fpdf + fontTools vendored")

mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"\n{out_path}: {mb:.1f} MB (v{version})")
