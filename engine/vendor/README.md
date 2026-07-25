# vendor/

Three files from the Rubix project, copied in verbatim so TWIST runs as a
standalone repository:

| File | What it provides |
|---|---|
| `utils.py` | move notation parsing, the face enum, `CUBE_SIZE` |
| `cube_state.py` | the move engine — layer rotation by physical coordinate |
| `cube_renderer.py` | OpenGL cubie drawing and the layer-rotation animation |

They are written against a fixed `CUBE_SIZE = 6`, but every function reads that
constant from module globals at call time. `engine/sizing.py` re-binds it to
retarget the whole engine at any size from 2 to 6 without forking these files —
which is exactly why they are vendored unmodified rather than edited.

Do not edit them here. Change them upstream in Rubix and re-copy, so the two
copies cannot silently diverge.
