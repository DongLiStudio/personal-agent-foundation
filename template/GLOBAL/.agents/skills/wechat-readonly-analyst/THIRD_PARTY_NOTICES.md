# Third-party notices

The bundled read-only engine is derived from material identified by the supplied package as `wechat-cli` 0.2.4 under Apache-2.0. The original package did not include a verifiable upstream commit; see `references/provenance.md`.

The offline wheelhouse contains unmodified Python wheels obtained from PyPI and verified by SHA-256 in `requirements.lock`:

- `click` 8.1.8 — BSD-3-Clause
- `colorama` 0.4.6 — BSD-3-Clause
- `pycryptodome` 3.23.0 — BSD/Public Domain components
- `zstandard` 0.23.0 — BSD
- `setuptools` 84.0.0 — MIT
- `wheel` 0.48.0 — MIT

Package metadata and license files remain inside their wheels. These packages are used only in the Skill-private runtime.
