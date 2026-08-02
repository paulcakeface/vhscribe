## Summary

Describe the user-visible or maintenance outcome.

## Validation

- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] `pytest -q`
- [ ] `docker compose config --quiet`
- [ ] Synthetic capture tested when the media path changed
- [ ] Documentation updated when behavior changed

## Safety and privacy

- [ ] No private media, `.env`, host paths, addresses, serial numbers, or secrets are included
- [ ] FFmpeg is still invoked without a shell
- [ ] The single capture-device owner and partial-file preservation invariants remain intact
- [ ] No privileged container or automatic public exposure was added

## Hardware evidence

State what was physically tested, if anything. Do not imply physical validation from synthetic CI.
