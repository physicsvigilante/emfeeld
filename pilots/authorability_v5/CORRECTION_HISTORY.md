# Evidence chronology

- All eight runnable JSON packets were frozen before first native execution and ran unchanged. Three controls were rejected as designed.
- A Python author-helper syntax typo was fixed before any packet was generated/frozen.
- The first same-author reference judge passed 38/39. Near-zero SC43 field cancellation left a float64 residual about 1.862645e-9 N/C between contributions of order 5.6 million N/C. The judge used an over-strict absolute-zero threshold 1e-10 N/C. A scale-aware 32-epsilon bound was used in the final verification, 39/39. No packet or engine was modified.
- A combined pytest run reached the execution timeout after displaying 100% but without reporting an exit code. It is not counted. The separately completed batches total 865 passed with no skips, warnings as errors.
- Two task outcomes require user-visible limitations: MC25 is numerical/local restoring-force evidence rather than automatic symbolic classification; SC43 uses an LLM-inferred answer supplied as a field probe.
- The exact chat-local first-run packets/results/hashes and both verifier versions live in the evidence ZIP; GitHub packets are semantically reserialized. No independent review is asserted.
