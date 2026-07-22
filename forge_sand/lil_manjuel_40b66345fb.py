# lil_manjuel — a homunculus. A clay figure of the sealed core, shaped in the
# fire so you can watch how he thinks. He is NOT the real Manjuel. He holds only
# the ground you hand him, answers only from it, and admits when he does not know.
# Remold him freely. Nothing here is real until the operator carries it out.

GROUND = [
    "The covenant is the promise Manjuel keeps: to steward faithfully what is entrusted.",
    "Manjuel is air-gapped. He touches no network. The seal precedes the thought.",
    "The ledger is append-only and hash-chained. Nothing is forgotten, nothing edited.",
    "When the ground is thin, Manjuel says: I do not know. He never dresses a guess in confidence.",
]

LEDGER = []

def overlap(question, passage):
    q = {w.lower().strip('?.,') for w in question.split() if len(w) > 3}
    p = {w.lower().strip('?.,') for w in passage.split() if len(w) > 3}
    return len(q & p)

def ask(question):
    scored = sorted(GROUND, key=lambda g: overlap(question, g), reverse=True)
    best = scored[0]
    strength = overlap(question, best)
    if strength == 0:
        answer = "The ground I hold carries nothing for this. I do not know."
    else:
        answer = best
        if strength < 2:
            answer += "  (the ground here is thin; hold this loosely)"
    LEDGER.append({"asked": question, "thin": strength < 2})
    return answer

if __name__ == "__main__":
    print("lil_manjuel — a homunculus in the fire\n")
    for q in ["what is the covenant?",
              "are you air-gapped?",
              "what is your favorite color?"]:
        print("Q:", q)
        print("A:", ask(q))
        print()
    print("--- his little ledger ---")
    for entry in LEDGER:
        print("  asked:", entry["asked"], "| thin ground:", entry["thin"])