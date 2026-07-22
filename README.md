# Steward
"""
MANJUEL — a local-only, offline-first sovereign intelligence system.
A stewardship engine.

    from manjuel import Manjuel
    m = Manjuel()
    m.awaken()
    print(m.ask("what is the covenant?"))

Properties, by construction:
  * AIR-GAPPED   — on awakening, every network road out of the process is
                   poisoned (socket, resolver, urllib, http.client). Any
                   attempt to reach outward raises SovereigntyBreach and is
                   written to the ledger. Nothing can be un-sealed.
  * SOVEREIGN    — all weights are grown in-process from the four
                   foundational documents (plus working memory). No foreign
                   model, no downloaded weight, no external tool, ever.
  * PYTHON-NATIVE— it is a library first: import it, hold its Answer
                   objects, extend it. The REPL is a courtesy on top.
  * AUDITABLE    — append-only, hash-chained ledger; a sealed covenant mark
                   (SHA-256 over the foundational documents) names each
                   epoch of the engine's life.

Dependencies: the Python standard library. Nothing else. Not even numpy.
"""
