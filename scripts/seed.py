import os

from jev_core.store import Store
from jev_workflows.scenarios import seed

if __name__ == "__main__":
    seed(Store(os.getenv("JEV_DB", "var/jev.sqlite")))
    print("Synthetic demo tenant seeded idempotently.")
