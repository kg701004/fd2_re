# FD2 reverse engineering and remake — durable agent rules

This file is the persistent operating contract for every agent working in this
repository. Read it before changing code, reverse-engineering claims, tests, or
documentation. `CLAUDE.md` records the project intent; this file is authoritative
for day-to-day execution.

## Goal and scope

- Reverse engineer the original *Flame Dragon 2* executable and data deeply
  enough to build an editable, clean-room remake engine.
- Recover hard-coded dialogue, acting, battle, postbattle, town, shop,
  preparation, party, and save behavior as editable data and typed rules.
- Preserve the original campaign as the fidelity mode, while allowing new
  campaigns to extend the engine later.
- A playable scaffold, debug route, decoded asset, or passing remake-only test is
  not completion. The original executable remains the behavioral oracle.

## Sources of truth

Read these in this order:

1. `README.md` — user-facing current status and verified screenshots.
2. `docs/knowledge-base/56-fd2-remake-sdd.md` — current system design and
   evidence policy.
3. `docs/knowledge-base/57-ui-evidence-matrix.md` — UI coverage and open gates.
4. `docs/knowledge-base/91-worklist.md` — current work queue.
5. `docs/knowledge-base/SESSION-HANDOFF-2026-07-06.md` — chronological evidence
   log; later corrections supersede earlier entries.

Historical design/WBS/reflection documents are not current-state authorities.
When they conflict with direct instructions, bytes, runtime captures, or the
files above, correct or explicitly mark the stale statement.

## Evidence rules

- Classify claims as proven, strong inference, hypothesis, or unknown.
- A proven binary claim needs an address/byte range plus caller or consumer; a
  proven visual claim needs an original runtime experiment or exact-state image
  comparison.
- Inspect direct instructions and raw jump-table words for high-impact control
  flow. Decompiler output and names are navigation aids, not proof.
- Do not promote raw bits, slots, globals, or return codes to semantic names
  until their writer and caller-specific consumer are both established.
- Keep unknown handler semantics fail-closed. Never wire guessed behavior into
  production merely to make the campaign advance.
- Walkthroughs are authored/player-visible corroboration, not an ABI or handler
  oracle.
- Clearly label debug-assisted, battle-skip, route-patched, screenshot-only, and
  direct-start experiments. They do not prove a normal player path.
- Original/remake screenshots must state whether they are exact-state,
  nearby-state, or layout-only. Do not mask unexplained pixels when claiming
  exact parity.
- Search the repository for stale assertions after closing or correcting a
  topic. Update SDD, evidence matrix, worklist, handoff, and README as relevant.

## Known project constraints and corrections

- Most battles lead to town/shop/preparation or another inter-battle segment,
  not directly to the next battle. Campaign tests must preserve these editable
  nodes and persistent party/save boundaries.
- `DATO_075` is a shop clerk.
- Do not invent a separate character “尤妮” from “悠妮”; verify glyphs, text
  index, portrait, and scene context. Her first appearance includes lying
  unconscious on the ground.
- The original hard-coded dialogue and handler behavior must become editable
  scripts/rules rather than permanent address-specific production hacks.

## Toolchain and host hygiene

- Keep pristine original game files immutable. Use a copied sandbox or writable
  overlay for DOSBox experiments and save mutation.
- Capstone is Docker-only via `tools/docker/fd2-cap.Dockerfile` and
  `fd2-cap-local`. Never install it in host Python, a global environment, or a
  host venv. `/tmp/fd2cap` must not exist.
- IDA is legally supplied at `/home/anr2/ida_94_official/dist`; use the
  maintained authorized Docker workflow. Do not redistribute IDA files.
- Prefer repository Dockerfiles and local reproducible images. Network-disabled
  runtime/test containers are preferred after dependencies are built.

### Docker cleanup is a hard rule

- Every one-shot FD2 container must use `docker run --rm`.
- Long commands must have a bounded lifecycle. Xvfb/background processes need a
  trap, and the owning container must exit when the command finishes.
- Immediately after each Docker RE, capture, build, or test batch, inspect
  `docker ps`/`docker ps -a` for FD2 containers. Stop and remove any no-longer
  needed container; never leave a test container consuming CPU between tasks.
- Inspect FD2 and dangling images after toolchain changes. Remove superseded or
  dangling images to avoid disk growth, but retain the single current
  reproducible image for each actively used toolchain. Never run a global prune
  that could delete another project's resources.
- Before handing off, record or verify that no unintended FD2 container remains
  running.

## Implementation and verification

- Prefer vertical slices: original bytes/state → typed decoder → rule → UI/save
  integration → deterministic test → original/remake comparison.
- A remake-only unit test proves internal consistency, not original fidelity.
- Use the normal unpatched player path as the final gate for campaign
  reachability, party persistence, shop/preparation, save/load, and ending.
- Run Go tests only in the maintained Docker image. Use `--rm`, network isolation
  where possible, manual bounded Xvfb lifecycle, and then verify container
  cleanup.
- Do not leave generated binaries or large temporary captures in the repository.
  Add only curated evidence artifacts useful to reviewers.

## Collaboration and commits

- Delegate bounded mechanical searches, tables, and assertion audits to a
  lower-cost subagent when explicitly permitted; the primary agent must inspect
  evidence, review diffs, and run final verification.
- Preserve unrelated user changes and never overwrite a dirty worktree.
- Staging is allowed during a round. Commit and push only after a substantial,
  evidence-backed update, not for cosmetic churn.
- Commit as `Codex <codex@openai.com>`.
- Before commit: run the relevant real regression, validate curated images and
  links, run `git diff --check`, inspect `git status` and the final diff.
- Push successful substantial rounds to `origin/main`, then verify local HEAD
  equals `origin/main`. Update GitHub-facing README/screenshots when the result
  materially changes visible status.

