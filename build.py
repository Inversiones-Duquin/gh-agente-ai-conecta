"""Build script v2 — empaqueta agente refactorizado para deploy S3/microVMs (Python 3.14)."""
import zipfile, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, "dist")
SITE = os.path.join(BASE, ".venv", "Lib", "site-packages")
os.makedirs(DIST, exist_ok=True)

# Next version
existing = [f for f in os.listdir(DIST) if f.startswith("agent-v") and f.endswith(".zip")]
nums = [int(f.replace("agent-v","").replace(".zip","")) for f in existing if f[7:-4].isdigit()]
version = max(nums) + 1 if nums else 230
out_path = os.path.join(DIST, f"agent-v{version}.zip")

# Root-level project files
ROOT_FILES = ["agent.py", "prompts.py", "helpers.py", "aws_clients.py", "requirements.txt"]

with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
    # 1. Root project files
    for fn in ROOT_FILES:
        fp = os.path.join(BASE, fn)
        if os.path.isfile(fp):
            zf.write(fp, fn)
            print(f"  + {fn}")

    # 2. mcps/i2dw/ directory
    mcps_dir = os.path.join(BASE, "mcps")
    for root, dirs, files in os.walk(mcps_dir):
        dirs[:] = [d for d in dirs if "__pycache__" not in d]
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            fp = os.path.join(root, fn)
            arc = os.path.relpath(fp, BASE).replace("\\", "/")
            zf.write(fp, arc)
    print(f"  + mcps/i2dw/")

    # 3. libs/ directory (six.py, typing_extensions.py)
    libs_dir = os.path.join(BASE, "libs")
    if os.path.isdir(libs_dir):
        for root, dirs, files in os.walk(libs_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.relpath(fp, BASE).replace("\\", "/")
                zf.write(fp, arc)
        print(f"  + libs/")

    # 4. Vendor all needed site-packages
    # Packages that are imported at runtime (direct or transitive)
    VENDOR = {
        # Core: Strands + Bedrock AgentCore
        "strands", "strands_agents-1.37.0.dist-info",
        "bedrock_agentcore", "bedrock_agentcore-1.6.4.dist-info",
        # AWS SDK
        "boto3", "boto3-1.42.96.dist-info",
        "botocore", "botocore-1.42.96.dist-info",
        "jmespath", "jmespath-1.1.0.dist-info",
        "s3transfer", "s3transfer-0.16.1.dist-info",
        # HTTP
        "requests", "requests-2.33.1.dist-info",
        "urllib3", "urllib3-2.6.3.dist-info",
        "certifi", "certifi-2026.4.22.dist-info",
        "charset_normalizer", "charset_normalizer-3.4.7.dist-info",
        "idna", "idna-3.13.dist-info",
        "httpx", "httpx-0.28.1.dist-info",
        "httpcore", "httpcore-1.0.9.dist-info",
        "h11", "h11-0.16.0.dist-info",
        "anyio", "anyio-4.13.0.dist-info",
        # Pydantic
        "pydantic", "pydantic-2.13.3.dist-info",
        "pydantic_core", "pydantic_core-2.46.3.dist-info",
        "pydantic_settings", "pydantic_settings-2.14.0.dist-info",
        "annotated_types", "annotated_types-0.7.0.dist-info",
        "typing_inspection", "typing_inspection-0.4.2.dist-info",
        # Starlette / SSE / Uvicorn
        "starlette", "starlette-1.0.0.dist-info",
        "sse_starlette", "sse_starlette-3.3.4.dist-info",
        "uvicorn", "uvicorn-0.46.0.dist-info",
        "click", "click-8.3.3.dist-info",
        "websockets", "websockets-16.0.dist-info",
        "watchdog", "watchdog-6.0.0.dist-info",
        # Utils
        "pyyaml", "pyyaml-6.0.3.dist-info",
        "python_dateutil-2.9.0.post0.dist-info", "dateutil",
        "python_multipart", "python_multipart-0.0.26.dist-info",
        "python_dotenv", "python_dotenv-1.2.2.dist-info",
        "pyjwt", "pyjwt-2.12.1.dist-info",
        "docstring_parser", "docstring_parser-0.18.0.dist-info",
        "packaging", "packaging-26.2.dist-info",
        "wrapt", "wrapt-2.1.2.dist-info",
        "importlib_metadata", "importlib_metadata-8.7.1.dist-info",
        "zipp", "zipp-3.23.1.dist-info",
        # JSON Schema
        "jsonschema", "jsonschema-4.26.0.dist-info",
        "jsonschema_specifications", "jsonschema_specifications-2025.9.1.dist-info",
        "referencing", "referencing-0.37.0.dist-info",
        "rpds", "rpds_py-0.30.0.dist-info",
        "attrs", "attrs-26.1.0.dist-info",
        # Crypto
        "cryptography", "cryptography-47.0.0.dist-info",
        "cffi", "cffi-2.0.0.dist-info",
        "pycparser", "pycparser-3.0.dist-info",
        # MCP (mcp-1.27.0 needed by bedrock_agentcore internals)
        "mcp", "mcp-1.27.0.dist-info",
        # OTEL
        "opentelemetry_api-1.41.1.dist-info",
        "opentelemetry_sdk-1.41.1.dist-info",
        "opentelemetry_semantic_conventions-0.62b1.dist-info",
        "opentelemetry",
        # Single-file vendored libs
        "six.py", "six-1.17.0.dist-info",
        "typing_extensions.py", "typing_extensions-4.15.0.dist-info",
    }

    # Directories to never include
    SKIP_DIRS = {"pip", "setuptools", "wheel", "fpdf", "xhtml2pdf", "reportlab",
                 "Pillow", "fontTools", "lxml", "html5lib", "cssselect2",
                 "__pycache__", ".git", "tests", "docs", "examples"}

    count = 0
    seen = set()
    for pkg in sorted(VENDOR):
        pp = os.path.join(SITE, pkg)
        if os.path.isdir(pp):
            for root, dirs, files in os.walk(pp):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    fp = os.path.join(root, fn)
                    arc = os.path.relpath(fp, SITE).replace("\\", "/")
                    if arc not in seen:
                        seen.add(arc)
                        zf.write(fp, arc)
                        count += 1
        elif os.path.isfile(pp):
            if pkg not in seen:
                seen.add(pkg)
                zf.write(pp, pkg)
                count += 1

    print(f"  + {count} vendored site-package files")

mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"\n{out_path}: {mb:.1f} MB (v{version})")
