"""Score a shot with no dependencies at all.

models/xg.json holds the shipped model as plain numbers -- eighteen means,
eighteen scales, eighteen coefficients and an intercept. Reading it here
means the live path needs neither sklearn nor a pickle it has to trust, and
anyone can open the file and see exactly what the model believes about a header
from the six yard box.

models/xg.shift.json, if present and active, adds one number to that
intercept. The model reads phrases and the phrases drift: the mapping from
"following a fast break" to a probability was fitted when that phrase meant
47% and by 2025-26 it meant 28%. The shift is refitted from shots already
played this season -- see src/recalibrate.py for why retraining cannot do this
and why waiting can. It is monotone, so it moves the level and leaves the
ranking exactly as it was.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(__file__), "..")


class Scorer:
    def __init__(self, path=None, shift_path=None, use_shift=True):
        m = json.load(open(path or os.path.join(ROOT, "models", "xg.json")))
        self.features = m["features"]
        self.mean, self.scale = m["mean"], m["scale"]
        self.coef, self.intercept = m["coef"], m["intercept"]
        self.shift, self.shift_meta = 0.0, None
        if use_shift:
            self._load_shift(shift_path or os.path.join(ROOT, "models",
                                                        "xg.shift.json"))

    def _load_shift(self, p):
        """A missing or not-yet-active shift file means no correction, not an
        error. Early in a season that is the correct behaviour."""
        if not os.path.exists(p):
            return
        s = json.load(open(p))
        self.shift_meta = s
        if s.get("active"):
            self.shift = float(s["shift"])

    def __call__(self, row):
        z = self.intercept + self.shift
        for f, mu, sd, w in zip(self.features, self.mean, self.scale, self.coef):
            z += w * ((row.get(f, 0) - mu) / (sd or 1.0))
        return 1.0 / (1.0 + math.exp(-z))
