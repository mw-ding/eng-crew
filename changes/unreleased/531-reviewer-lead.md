# Reviewer lead owns its pool

- Add a long-lived reviewer lead in reserved window 3 with durable handoffs,
  serialized replay, cap/load/suite admission and one-restart supervision.
- Route review, validation, recheck escalation and terminal reclaim through
  the lead; recover missing validation after review cleanup and deduplicate
  passes without changing synthesizer verdict portability.
- Treat failed Actions jobs with no started steps as infrastructure incidents;
  allow validation while keeping green CI required for landing.
