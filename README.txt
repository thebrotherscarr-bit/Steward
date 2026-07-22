========================================================================
  MANJUEL — the estate.  What's here, and how to wake it.
========================================================================

TO START:
  Double-click START.bat
  -> wakes Steward (who seals Manjuel beneath him) on :7374
  -> lights the Forge (serves your console) on :7375
  -> opens the console in your browser at localhost:7375
  Close the window to bring the whole estate down. The ledger holds.

------------------------------------------------------------------------
THE LIVE PIECES (what actually runs):
------------------------------------------------------------------------
  manjuel.py        the sealed core. remembers, judges, never acts.
  steward.py        the gateway. reasons, weighs, directs. runs on :7374,
                    spawns manjuel sealed beneath him.
  forge_server.py   the workshop + the board's face. runs on :7375,
                    serves console.html, calls the three below as modules.
  board.py          the coordinator. holds tools, records use, weighs the
                    stack, holds the mission inbox.
  mission.py        the mission loop: before-plan / observe / after-review.
  assault_pack.py   the mission base: loads, gates, moves the littles.
  console.html      the operator console (the face). served by the forge.
  START.bat         the launcher. raises it all, opens the one page.

------------------------------------------------------------------------
THE DOCTRINE (who each part is — feed these; they are the ground):
------------------------------------------------------------------------
  foundation/          manjuel's 4 (+ 05_THE_HAND) -> put beside manjuel.py
  steward_foundation/  steward's 3
  forge_foundation/    the forge's 1
  board_foundation/    the board's 1

  IMPORTANT: manjuel's documents must sit in a folder named  foundation/
  right next to manjuel.py, or he will not awaken.

------------------------------------------------------------------------
THE CONSOLE (what the buttons do):
------------------------------------------------------------------------
  ASK HIM (top)     peek into the core — ask Manjuel directly
  ASK (center)      chat the core through Steward
  RESEARCH (center) Steward's full loop: plan -> weighed models -> ruling
  SHAPE + RUN       make a figure in the fire; then REMOLD / SMOOTH /
                    CARRY OUT (carry-out writes a real file — only you can)
  DEPLOY MISSION    purpose/scope/little/time -> deploy; watch the ticker
  SCRATCH           deploy notes, kept on the board

------------------------------------------------------------------------
THE ONE RULE THAT KEEPS IT SAFE:
------------------------------------------------------------------------
  Nothing becomes real unless YOU make it real. Manjuel is sealed and
  handless. Steward is scoped and gated. The Forge holds the fire; only
  the operator carries anything out of it. The board commands only clay,
  and clay does not last. Authority never leaves your hand.

  Manjuel remembers everything and invents nothing. That is the whole point.
========================================================================
