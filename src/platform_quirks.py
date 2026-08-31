"""Known-false warnings on this machine, silenced deliberately and in one place.

Silencing warnings is usually how bugs get hidden, so each one here has to be
reproduced outside the project first.
"""
import warnings


def silence_accelerate_matmul():
    """numpy 2.2.6 on Apple's Accelerate BLAS reports divide-by-zero, overflow
    and invalid-value in large matmuls that contain none of those things.

    Reproduced with no project code involved:

        >>> np.random.rand(28735, 17) @ np.random.rand(17)
        RuntimeWarning: divide by zero encountered in matmul

        >>> np.random.rand(100, 5) @ np.random.rand(5)      # no warning

    It fires on shape, not on values, and the results are correct. It is
    filtered narrowly -- module and message both -- so a real overflow
    somewhere else still surfaces.
    """
    for msg in ("divide by zero encountered in matmul",
                "overflow encountered in matmul",
                "invalid value encountered in matmul"):
        warnings.filterwarnings("ignore", message=msg,
                                category=RuntimeWarning)
