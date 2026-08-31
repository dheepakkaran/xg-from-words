"""Score a shot with no dependencies at all.

models/xg.json holds the shipped model as plain numbers -- seventeen means,
seventeen scales, seventeen coefficients and an intercept. Reading it here
means the live path needs neither sklearn nor a pickle it has to trust, and
anyone can open the file and see exactly what the model believes about a header
from the six yard box.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(__file__), "..")


class Scorer:
    def __init__(self, path=None):
        m = json.load(open(path or os.path.join(ROOT, "models", "xg.json")))
        self.features = m["features"]
        self.mean, self.scale = m["mean"], m["scale"]
        self.coef, self.intercept = m["coef"], m["intercept"]

    def __call__(self, row):
        z = self.intercept
        for f, mu, sd, w in zip(self.features, self.mean, self.scale, self.coef):
            z += w * ((row.get(f, 0) - mu) / (sd or 1.0))
        return 1.0 / (1.0 + math.exp(-z))
