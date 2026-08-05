# D2T-RNA reproducibility image.
#
# Builds a clean container that (1) installs the package from a clean copy,
# (2) emits the registered real-data certificate (add riboswitch, PDB 1Y26),
# and (3) runs the locked unit tests.  This reproduces the paper's
# reproducible-artifact claim (Section \ref{sec:real}, Supp. \ref{sec:supp-real})
# without any server-local state.
#
#   Build:  docker build -t d2t-rna/paper-artifact .
#   Run:    docker run --rm d2t-rna/paper-artifact
#
FROM python:3.11-slim

WORKDIR /app

# Package source + `pytest` for the locked tests.
#
# The paper's reproducible artifact is the registered real-data certificate
# (add riboswitch, PDB 1Y26) and the locked T2 test suite, whose decision-theoretic
# path (custom rational simplex) is pure Python stdlib (fractions / decimal).
# We therefore install with --no-deps to keep the image small and the build fast
# and self-contained.  pyproject.toml additionally declares numpy/scipy/pydantic,
# which are used by other (non-certificate) package modules; drop --no-deps if
# the full package is required.
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests

RUN pip install --no-cache-dir --no-deps -e . \
    && pip install --no-cache-dir pytest

# Write certificates to a container-local path (env-configurable, see
# scripts/real_add_run.py).
ENV D2T_RNA_ARTIFACTS_ROOT=/app/artifacts

# Locked verification at build time: emit the real-data certificate stack and
# run the locked unit tests.  A build fails if either step fails.
RUN python scripts/real_add_run.py \
    && python -m pytest tests/t2/test_real_add.py -q

# Default entrypoint: rerun the locked T2 test suite.
CMD ["python", "-m", "pytest", "tests/t2/", "-q"]