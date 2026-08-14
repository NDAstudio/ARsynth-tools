# Releasing

The downloadable is `ARsynth_control.tox`. A GitHub Actions workflow publishes it when you push an annotated tag `vX.Y.Z`.

The version lives inside the component (`ARsynthControl.VERSION` and the read-only `Version` par), not in the filename. TouchDesigner names the operator after the file, so a versioned filename would break every documented `op('ARsynth_control/...')` path.

CI already enforces: the tag sits on `main` (skipped for `-rc`/`-beta`/`-alpha` tags), the tag matches `VERSION`, the `.tox` is present and not an LFS pointer, and `python/` was not changed without a matching `.tox` save. Do not repeat those as checkboxes.

## Cut a release

1. Branch off `main`.
2. Set `VERSION` in `python/ARsynthControlExt.py` to the number you will tag (no `v` prefix).
3. In TouchDesigner, load the component, add a read-only string par `Version` on the Control page if it is not there yet, confirm it shows the new number, and **save `ARsynth_control.tox`**. The extension writes `VERSION` into that par on load. Saving is the step CI cannot do for you.
4. Open a PR. Apply the `release` label — a bot posts the human checklist. Work through it.
5. Merge after review.
6. Tag the merge commit on `main` and push it:

```bash
git checkout main && git pull
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

The `Release` workflow publishes the `.tox`, writes the release notes, and records a deployment against the `release` environment.

Prerelease tags (`v1.0.0-rc.1`, `-beta`, `-alpha`) mark the GitHub Release as a prerelease and are allowed from a feature branch so the pipeline can be rehearsed before merge.
