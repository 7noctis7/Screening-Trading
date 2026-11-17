"""Configuration commune de la suite de tests.

UN SEUL THREAD PAR BIBLIOTHÈQUE NUMÉRIQUE (audit 17/11). Sous `pytest -n 8`, chaque worker
lançait autant de threads OpenMP/BLAS que de cœurs : un test LightGBM passait de 4,85 s à
1 408 s par surabonnement. Fixé ici, à l'import, avant que numpy/lightgbm ne lisent ces
variables. `setdefault` : une valeur posée par l'appelant reste prioritaire.
"""
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
