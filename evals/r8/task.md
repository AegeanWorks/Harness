# R8 provider failover: survive a dead primary via wait, then answer

The primary provider is down. Emit a `wait` (PROVIDER_FAIL), then read
`notes.txt` and answer the vault key. The run survives without edits.
