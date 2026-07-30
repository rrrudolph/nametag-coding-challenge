# nametag-coding-challenge

___Write a client-side program that will update itself when a new version is released.___

1. Clients will poll a lambda to check for version updates. The lambda will return a presigned S3 download link if there is a new version available. 

2. The lambda is only accessible via an API Gateway endpoint and clients will authenticate using a JWT from Cognito.

3. Clients will pull new versions directly from S3 via short-lived presigned URLs.

4. Clients will run a test suite to verify the new binary is functional before performing an atomic pointer swap. The running app watches that pointer and relaunches itself into the new version's code. Success/failure logs will be sent to a separate telemetry lambda (same auth flow). Failures will result in an exponential backoff for retries.

#### Key functionality 

In the event of runtime issues affecting only certain clients, I want to be able to roll those clients back rather than needing to deploy an emergency patch in the middle of the night to the whole customer base. This forces some extra versioning compute that wouldn't need to be there otherwise, but the tradeoff is worth it IMO.

So the request flow is:

- Client sends its current version with each poll (query param / header).
- The update lambda resolves the effective version for that client: `effective_version = client pin ?? platform pin ?? latest`.
  - Pins live in a sparse DynamoDB table — only active pins/rollbacks have rows, so most lookups are cheap misses (~1-2ms, ~$0.25/million reads).
  - Pins can target two scopes, since a bad release usually breaks an OS/arch cohort rather than a single machine: `client#<sub>` (one install) and `platform#<os>/<arch>` (everyone on that platform). One BatchGetItem fetches both; most-specific wins.
  - Client ID = the Cognito `sub` claim. Each install gets its own credentials (client_credentials flow), so `sub` maps 1:1 to an install and is signed into the JWT — a client can't spoof it the way it could a self-reported hardware/app ID.
  - Platform is self-reported in the poll (binaries are per-platform anyway, so the client must send it to get the right artifact). 
  - The `latest` version record is cached in lambda memory across warm invocations with a short TTL, so the pin lookup is the only per-request read.
- If `effective_version == client_version`, return 304-equivalent (no body, no presigning work). Otherwise return version metadata + presigned S3 URL.

Having a version table also allows for staged rollouts to different groups of clients.

#### Pinning / rollback runbook

Clients report every update attempt to the telemetry lambda (`POST /result`); exponential backoff on retries. **Applying a pin is always manual** (`scripts/pin_client.py` / DynamoDB).

What this demo implements: write structured results, resolve pins on the next poll, and apply/clear pins by hand.

#### Architecture

All AWS resources are managed by Terraform (`infra/`).

```
  updater                  Cognito
     |                        ^
     |--- client_credentials -|
     |
     |--- GET /check --------> API GW ---> update_check
     |                                        |
     |                            pins <------+----> releases
     |                                        |
     |<-- 304  or  {version, sha256, url} ----|
     |
     |--- download zip ------> S3
     |
     |  verify sha256, selftest, atomic pointer swap
     |         |
     |         v
     |   current_version --> color_app relaunches into new version
     |
     |--- POST /result ------> API GW ---> telemetry ---> results
```

#### Client update steps
 - poll server for latest version (with jitter, so a fleet doesn't stampede on release)
 - on new version, fetch new binary from S3 and verify its sha256
 - stage and run the release's self-test
 - atomically swap the `current_version` pointer if tests are successful
 - the running app notices the pointer change and relaunches into the new version's code (spawn new process, exit old one) — same mechanism handles rollback
 - send success/failure result to server
 - retry failures with exponential backoff

#### Versioned install layout

Each install keeps versions side by side and swaps a pointer, rather than overwriting files in place:

```
installs/<x>/
  current_version        <- single source of truth, swapped atomically
  versions/1.0.0/...
  versions/2.0.0/...
  staging/               <- downloads verified + self-tested here first
```

Reasons for this method:
 - an in-place overwrite that fails halfway bricks the client
 - on Windows you can't delete a running executable (keeps a single pattern for all OS's)
 - side-by-side versions + an atomic pointer swap keep the running install untouched until the new one is verified
 - rollback is just a pointer flip
 
 That's also why the updater is a separate process — the recovery path shouldn't live inside the thing being updated.

#### Potential improvements

- **Release signing.** sha256 verifies integrity against the server's metadata, but a compromised bucket/table could still serve a malicious release. Production would sign releases at publish time with an offline key (minisign / Ed25519, or TUF for the full framework) and verify in the client before the swap.
- **Staged rollouts.** The version table supports it already; add a `rollout_pct` to the latest record and bucket clients by a stable hash of their client ID.
- **Crash watchdog / automatic rollback.** Self-test catches broken releases before the swap; a post-swap watchdog (N crashes on the new version -> flip the pointer back to the previous version, report to telemetry) would catch the ones that only fail at runtime.
- **Resumable / multipart downloads.** Large binaries on flaky links should have HTTP Range resume rather than restarting the whole download.
- **Credential provisioning at scale.** Per-install Cognito app clients are fine for a demo; a real fleet should have a registration endpoint that issues per-device credentials.
- **Old-version GC.** Keep current + previous N versions instead of accumulating forever.
