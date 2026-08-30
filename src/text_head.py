"""Track B as the proposal specifies it: a small PyTorch head over frozen
sentence embeddings.

Capacity is deliberately small. 22k rows behind a frozen encoder does not
support anything larger, and the linear probe in run_experiment.py is the
control that says whether the extra capacity buys anything at all.
"""
import numpy as np
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, ClassifierMixin


class MLPHead(ClassifierMixin, BaseEstimator):
    def __init__(self, hidden=128, dropout=0.3, epochs=30, lr=1e-3,
                 weight_decay=1e-4, batch=512, patience=5, seed=0):
        self.hidden = hidden
        self.dropout = dropout
        self.epochs = epochs
        self.lr = lr
        self.weight_decay = weight_decay
        self.batch = batch
        self.patience = patience
        self.seed = seed

    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        torch.manual_seed(self.seed)
        self.classes_ = np.arange(int(y.max()) + 1)
        self.mu_, self.sd_ = X.mean(0), X.std(0) + 1e-6

        # last 10% of rows (already date-ordered) as the early-stopping split
        cut = int(len(X) * 0.9)
        Xtr, ytr = self._prep(X[:cut]), torch.tensor(y[:cut])
        Xva, yva = self._prep(X[cut:]), torch.tensor(y[cut:])

        self.net_ = nn.Sequential(
            nn.Linear(X.shape[1], self.hidden), nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden, len(self.classes_)))
        opt = torch.optim.AdamW(self.net_.parameters(), lr=self.lr,
                                weight_decay=self.weight_decay)
        lossf = nn.CrossEntropyLoss()

        best, best_state, bad = float("inf"), None, 0
        n = len(Xtr)
        for _ in range(self.epochs):
            self.net_.train()
            perm = torch.randperm(n)
            for i in range(0, n, self.batch):
                idx = perm[i:i + self.batch]
                opt.zero_grad()
                loss = lossf(self.net_(Xtr[idx]), ytr[idx])
                loss.backward()
                opt.step()
            self.net_.eval()
            with torch.no_grad():
                v = lossf(self.net_(Xva), yva).item()
            if v < best - 1e-4:
                best, bad = v, 0
                best_state = {k: t.clone() for k, t in self.net_.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state:
            self.net_.load_state_dict(best_state)
        return self

    def _prep(self, X):
        return torch.tensor((np.asarray(X, dtype=np.float32) - self.mu_) / self.sd_)

    def predict_proba(self, X):
        self.net_.eval()
        with torch.no_grad():
            return torch.softmax(self.net_(self._prep(X)), dim=1).numpy()

    def predict(self, X):
        return self.predict_proba(X).argmax(1)
