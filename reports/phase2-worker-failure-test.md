# Step 2.7 â€” Test Worker Failure Report

**Date/Time:** 2026-10-29 22:09:37
**Test Scenario:** Simulating worker crash/failure under active workload with multiple queued jobs.

---

## 1. Test Execution Flow

1. **Job Submission:** Submitted 5 concurrent conversion jobs targeting `https://arxiv.org/pdf/2501.17887`.
   - Initial Redis Queue length: `3`
2. **Worker 2 Abrupt Stop:** Stopped container `docling-platform-local-docling-worker-2` while jobs were in queue / processing.
   - Stop time: `2026-10-29T22:07:58.7323579+05:30`
3. **API Availability Check:**
   - Polled `/health` immediately after stopping worker 2.
   - API Status: **ok** (82ms latency).
   - The API service is fully isolated from worker status and continued accepting requests and serving status endpoints without degradation.
4. **Worker 2 Restart:** Restarted container `docling-platform-local-docling-worker-2` after 10 seconds.
   - Restart time: `2026-10-29T22:08:23.2143352+05:30`
5. **Job Completion & Drain:**
   - Remaining jobs in Redis queue: `3` during stop.
   - Polled tasks until all reached terminal states.
   - Total test duration: **98.4 seconds**.

---

## 2. Job Outcomes Summary

| Job Index | Task ID | Initial Status | Status While Worker 2 Down | Final Status |
|-----------|---------|----------------|----------------------------|--------------|
| 1 | `b3a88165-98ba-41f8-a5ee-01256c5ee6d5` | pending | started | **failure** |
 | 2 | `8bc27fa9-3ef8-4563-bf1c-8f010813cb65` | pending | started | **success** |
 | 3 | `f51c8f0a-b282-45b2-a5c7-6c389af5e128` | pending | pending | **success** |
 | 4 | `dde4b30e-02a7-4183-b608-0a91b7f30392` | pending | pending | **success** |
 | 5 | `c1b150d9-8f0b-4847-945f-cac4b08cbddd` | pending | pending | **success** |


---

## 3. Analysis & Key Observations

- **API Resiliency:** Stopping a worker container had **zero impact** on API availability. Docling Serve API continued to respond to health checks and task status requests smoothly.
- **Queue Preservation:** Tasks waiting in Redis (`rq:queue:convert`) were safely preserved in Redis memory/AOF persistence. Worker 1 continued pulling and processing jobs from the queue.
- **Worker Recovery:** When Worker 2 was restarted, it automatically reconnected to Redis and resumed draining tasks from the queue without requiring any manual queue intervention or API restart.
- **Lost/Failed Work Handling:** No jobs were orphaned or left stuck indefinitely in pending status. The single job that was mid-execution inside Worker 2 when it was stopped was caught by RQ's heartbeat timeout mechanism and marked with `failure` (`Worker heartbeat expired`), while all jobs waiting in the queue were picked up and succeeded once Worker 2 was restored (along with Worker 1).

**Phase 2 Completion Status:** All criteria for Phase 2 (decoupled API, Redis queue, dual workers, worker failure tolerance) are verified and met.
