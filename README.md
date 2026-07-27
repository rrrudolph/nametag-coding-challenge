# nametag-coding-challenge

___Write a client-side program that will update itself when a new version is released.___

1. Clients will poll a lambda to check for version updates. The lambda will return a presigned S3 download link if there is a new version available. 

2. The lambda will only be accessible via an API Gateway endpoint and clients will authenticate using a JWT from Cognito.

3. Clients will pull new versions from S3 using multipart downloads. 

4. Clients will run a test suite to verify the new binary is functional before performing an atomic file swap. Success/failure logs will be sent to a separate telemetry lambda (same auth flow). Failures will result in an exponential backoff for retries.

#### Key functionality 

In the event of runtime issues affecting only certain clients, I want to be able to roll those clients back rather than needing to deploy an emergency patch in the middle of the night to the whole customer base. This forces some extra versioning compute that wouldn't need to be there otherwise, but the tradeoff for resiliency is worth it IMO.

So the request flow is:

- Client sends its current version with each poll (query param / header).
- The update lambda resolves the effective version for that client: `effective_version = client pin ?? platform pin ?? latest`.
  - Pins live in a sparse DynamoDB table — only active pins/rollbacks have rows, so most lookups are cheap misses (~1-2ms, ~$0.25/million reads).
  - Pins can target two scopes, since a bad release usually breaks an OS/arch cohort rather than a single machine: `client#<sub>` (one install) and `platform#<os>/<arch>` (everyone on that platform). One BatchGetItem fetches both; most-specific wins.
  - Client ID = the Cognito `sub` claim. Each install gets its own credentials (client_credentials flow), so `sub` maps 1:1 to an install and is signed into the JWT — a client can't spoof it the way it could a self-reported hardware/app ID.
  - Platform is self-reported in the poll (binaries are per-platform anyway, so the client must send it to get the right artifact). Lying about platform only gets you the wrong binary — not an escalation.
  - The `latest` version record is cached in lambda memory across warm invocations with a short TTL (30-60s), so the pin lookup is the only per-request read.
- If `effective_version == client_version`, return 304-equivalent (no body, no presigning work). Otherwise return version metadata + presigned S3 URL.

Having a version table also allows for staged rollouts to different groups of clients.

#### Pinning / rollback runbook

Detection is automated; applying a pin is manual. Auto-pinning on raw failure volume is how you roll an entire cohort back because one client filled its disk.

1. **Detect** — telemetry lambda writes structured results (version, platform, success, error). Metric filters / alarms fire when failure rate for a `(version, platform)` exceeds a threshold, or when a single client fails N times on the same version.
2. **Alert** — SNS → Slack/PagerDuty with the suggested scope already computed:
   - many clients on the same platform failing → suggest `platform#<os>/<arch>`
   - one client failing → suggest `client#<sub>`
   Include the last-known-good version (previous `latest` for that platform) so the apply step is fill-in-the-blank.
3. **Decide** — human confirms: is this a bad binary vs. environmental (disk full, network)? Wrong call → don't pin; let client backoff handle it. Right call → pick scope + target version.
4. **Apply** — write one DynamoDB item to the pin table (CLI / small admin script / console). No redeploy. Item should carry `pinned_by`, `reason`, `pinned_at`, and a **TTL** (e.g. 7 days) so forgotten pins don't leave a cohort stuck forever.
5. **Verify** — next poll from affected clients returns the pinned version; telemetry should show them succeeding (or at least no longer failing on the bad version).
6. **Clear** — when a fixed release ships and becomes `latest`, delete the pin rows (or let TTL expire). Client pins that intentionally stay behind can be re-affirmed.

Optional later: one-click "apply suggested pin" from the alert, still requiring a human click — not a fully automatic write.

#### Server Infra
 - Cognito 
 - API Gateway
 - Update lambda 
 - Telemtry lambda
 - DynamoDB
 - S3

#### Client update steps
 - poll server for latest version
 - on new version, fetch new binary from S3
 - install and run tests 
 - swap to new version if tests are succesful 
 - send success/failure result to server
 - retry failures with exponential backoff
