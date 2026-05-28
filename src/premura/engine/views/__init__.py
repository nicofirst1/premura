"""Stage 2 resolver modules — homes for concrete input resolvers.

This package is the static in-tree home for the resolver implementations that
turn declared dependencies into resolved inputs (see
:mod:`premura.engine._resolution`).

This package now hosts the first two concrete resolver modules:
``observation.py`` (observation-history resolver) and ``profile.py``
(profile-as-of resolver). Importing :mod:`premura.engine` must NOT import any
module here eagerly; the public surface loads them lazily via
``_ensure_builtin_resolvers_loaded()`` the first time a caller resolves a
dependency.

Future supported domains are added by:

1. dropping a module here that calls ``@resolver(domain="...")`` at import
   time, and
2. appending the module's dotted name to
   ``premura.engine._BUILTIN_RESOLVER_MODULES``.

No filesystem scanning, no entry points, no plugin loader. Reviewers can trace
the full set of supported domains by reading those two locations.
"""
from __future__ import annotations
