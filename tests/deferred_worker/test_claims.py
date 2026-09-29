"""Direct tests for jobs/deferred_worker/claims.py, the worker's MIRROR of
src/database/claims.py. The worker's event tests mock this module out, so
without these its behaviour would be untested."""
import unittest

import claims as worker_claims
from tests.database.test_claims import ClaimLifecycleContract


class TestWorkerClaimLifecycle(ClaimLifecycleContract, unittest.TestCase):
    claims_module = worker_claims

    def test_resolves_to_the_worker_twin_not_src(self):
        # Guards the contract above against silently testing src twice.
        self.assertTrue(worker_claims.__file__.replace("\\", "/").endswith("jobs/deferred_worker/claims.py"))


if __name__ == "__main__":
    unittest.main()
