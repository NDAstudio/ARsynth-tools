# ARSynth Control

[![Release](https://img.shields.io/github/v/release/NDAstudio/ARsynth-tools)](https://github.com/NDAstudio/ARsynth-tools/releases/latest)

A TouchDesigner component for switching [ARSynth](https://arsynth.cc) AR scenes.

ARSynth is a platform for AR at live events: you compose scenes in a browser, and the
audience sees them by pointing a phone at a QR code. A *show* is a QR code that points
at whichever *scene* is currently active — swap the scene and everyone's phone
follows.

This component does that switch from inside TouchDesigner, so the AR layer can be
part of a show cue instead of something you click in a browser tab mid-set.

---

## Install

1. Download [`ARsynth_control.tox`](https://github.com/NDAstudio/ARsynth-tools/releases/latest/download/ARsynth_control.tox).
2. Drag it into your project.
3. Fill in your ARSynth email and password on the **Connection** page and click
   **Log in**.

Built and tested on TouchDesigner 2025.33070 on macOS. No external Python packages.

---

## Parameters

### Control

| | |
|---|---|
| Show | Which show you are driving. |
| Scene | The active scene. Changing this switches it for the audience. |
| Active scene | Read-only. What ARSynth reports as live. |
| Scene number | The active scene as a number. Read it, or write it to switch. |
| Refresh now | Re-read shows and scenes. |
| Auto refresh + Interval | Poll, so a scene switched elsewhere shows up here. |

### Connection

Supabase URL and anon key are filled in for hosted ARSynth; change them only if you
self-host. Your email and password go here.

Access tokens are kept in memory and are never written into a saved `.toe` or `.tox`.
Your **password is** saved with the file, like any string parameter — so don't commit
a project with your credentials filled in.

---

## Driving your Touchdesigner visuals

The active ARsynth scene's number is available as a number in the component and as a constant CHOP

```python
op('ARsynth_control/scene_index')['scene'] 
```

It matches the order of the Scene menu. Write to the parameter from an expression, a
CHOP export, a MIDI mapping or a script and the AR scene follows. Out-of-range values
are ignored.

Setting the scene here sends it to ARSynth. If someone switches the scene from the
web dashboard instead, the number updates on the next refresh so you can see it, but
nothing in your network is moved for you.

The component's viewer shows the selected show's QR code, and `out1` gives you that
QR as a TOP.

---

## Repo layout

```
ARsynth_control.tox     the component
python/                 the component's Python, as readable .py files
```

A `.tox` is binary, so Git can't show you what changed inside one. The `python/`
files are the same code that lives in the component's DATs, exported so it can be
read and diffed. If you change the Python, change it there and load it back into the
DATs.

---

## Contributing

Early days — issues and questions welcome. If you want to change the component
itself, please open an issue first: `.tox` files can't be merged by Git, so two
people editing one in parallel means someone's work is lost.

## Release

1. Bump `ARsynthControl.VERSION` in `python/ARsynthControlExt.py`.
2. In TouchDesigner, make sure the component's read-only `Version` par shows the
   same value, then save `ARsynth_control.tox`.
3. Open a PR and confirm the release checkbox in the PR template.
4. Merge to `main`, then tag and push:

```bash
git checkout main && git pull
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

## Credits

Built by NDA/studio during the [Open Culture Tech](https://www.openculturetech.com/)
residency, 2026.

ARSynth is by [Superposition](https://github.com/superpositioncc). This component is
an independent client and is not affiliated with them.

## License

MIT — see [LICENSE](LICENSE).
