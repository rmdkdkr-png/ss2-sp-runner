# WebGL canvas is created with `alpha: true` — costs ~8 fps and 20× more frame hitches while the screen is being touched

## Summary

The canvas EmulatorJS hands to the emscripten runtime ends up with a **translucent**
WebGL context (`alpha: true`, `premultipliedAlpha: true`). The browser compositor
therefore has to **blend the emulator canvas against the page on every composite**.

That blend is cheap when nothing else is happening. It is not cheap while the user is
touching the screen — the compositor is already busy, and the extra layer starves the
emulator loop. On a mobile-sized viewport I measured **51.8 → 59.6 fps** and
**65 → 3 long frames** (>33 ms) just from forcing the context opaque.

Nothing else changed. No emulator, core, shader, or setting was touched.

## Measurements

412×915 viewport, NGP core (beetle-ngp), same ROM, same in-game scene.
Each condition run twice, 8 s each. `emu_fps` is the delta of
`gameManager.getFrameNum()` per second — i.e. **frames the emulator actually ran**,
not frames the browser painted.

**Dragging a finger across the on-screen d-pad:**

| | emu fps | long frames (>33 ms) |
|---|---|---|
| default (`alpha: true`) | 51.8 / 51.9 | 65 / 64 |
| **`alpha: false`** | **59.6 / 59.6** | **3 / 2** |

**Full scenario sweep, before → after:**

| scenario | before | after |
|---|---|---|
| idle | 59.8 fps / 0 hitches | 59.8 / 0 |
| d-pad drag | 52.6 / 57 | **59.3 / 2** |
| face button mash | 59.2 / 5 | **59.9 / 0** |
| macro button mash | 56.4 / 26 | **59.4 / 4** |
| both at once | — | **59.6 / 3** |
| shader `2xScaleHQ` | 49.1 / 86 | **59.5 / 1** |
| shader `4xScaleHQ` | 44.7 / 118 | 50.9 / 70 |

Note the shader rows. **Most of what looked like shader cost was this blend
compounding with the shader passes.** Only 4xScaleHQ remains genuinely expensive.

### Control experiment — it is not the page's event handlers

My app has touch handlers on its own on-screen controls, so the obvious suspect was my
own JS. I dragged over the **emulator canvas instead**, which has no handlers of mine
at all:

| | emu fps | long frames |
|---|---|---|
| idle | 58.8 / 58.8 | 8 / 9 |
| drag over my d-pad (handlers present) | 51.4 / 50.7 | 70 / 74 |
| **drag over bare canvas (no handlers)** | **43.5 / 44.0** | 123 / 118 |

The surface with **no** handlers was slower. The cost is in compositing, not in
JavaScript event handling.

## Why

`emscripten_webgl_init_context_attributes()` defaults to `alpha = true` and
`premultipliedAlpha = true`, and as far as I can tell nothing in the RetroArch
emscripten context path overrides them. Verified at runtime:

```js
document.querySelector('#game canvas')
  .getContext('webgl2').getContextAttributes()
// { alpha: true, premultipliedAlpha: true, depth: true, stencil: true, ... }
```

An emulator canvas is fully opaque by construction — every pixel is written every
frame. There is nothing behind it that should ever show through.

## Suggested fix

The context is created inside the wasm module, so `Module.webglContextAttributes`
does not reach it (RetroArch calls `emscripten_webgl_create_context` directly rather
than going through `Browser.createContext`). Two places this could be fixed properly:

1. **In the RetroArch emscripten context driver** — set `attrs.alpha = false;
   attrs.premultipliedAlpha = false;` where the WebGL context is created. This is the
   correct fix and would need to land in the build repo.
2. **In `emulator.js`, around where the canvas is created and passed to
   `EJS_Runtime({ canvas: this.canvas, ... })`** — wrap `getContext` for the lifetime
   of module startup so the attributes are forced regardless of what the wasm asks for.

I do not know the codebase well enough to say which you'd prefer, so I have not opened
a PR. Happy to write either one if a maintainer points at the right file.

## Workaround anyone can apply today

Drop this in **before** the loader script runs:

```js
(function () {
  const proto = HTMLCanvasElement.prototype, orig = proto.getContext;
  proto.getContext = function (type, attrs) {
    if (type === "webgl" || type === "webgl2" || type === "experimental-webgl") {
      attrs = Object.assign({}, attrs || {}, { alpha: false, premultipliedAlpha: false });
    }
    return orig.call(this, type, attrs);
  };
})();
```

I deliberately keep this patch installed for the whole session rather than reverting it
after boot, because the GL context can be recreated (shader switch, fullscreen) and it
must be opaque then too. It only touches two attributes and only for WebGL contexts.

If you need the canvas to actually be see-through — a page that renders something
behind it — this obviously is not for you. I would guess that is rare.

## How to reproduce

```js
// paste in the console once the game is running
window.__p = { t: [], last: 0, on: false };
(function tick(t) {
  if (__p.on) { if (__p.last) __p.t.push(t - __p.last); __p.last = t; }
  requestAnimationFrame(tick);
})();
__p.start = () => { __p.t.length = 0; __p.last = 0; __p.on = true;
  __p.f0 = EJS_emulator.gameManager.getFrameNum(); __p.w0 = performance.now(); };
__p.stop = () => { __p.on = false;
  const dt = (performance.now() - __p.w0) / 1000;
  const df = EJS_emulator.gameManager.getFrameNum() - __p.f0;
  return { emu_fps: +(df / dt).toFixed(1),
           hitches: __p.t.filter(x => x > 33).length }; };
```

`__p.start()`, drag a finger (or hold the mouse button and move) over the canvas for
~8 s, `__p.stop()`. Then reload with the workaround above and repeat.

### A live page you can try

I run the patched build here — a single-file EmulatorJS front-end (4.2.3, `ngp` core):

**https://rmdkdkr-png.github.io/ss2-sp-runner/**

It needs your own ROM (nothing is bundled), but any NGP/NGPC ROM will do — the effect is not
game-specific. That page already has the patch applied, so
`getContext('webgl2').getContextAttributes()` reports `alpha: false` there. For the
unpatched side of the comparison, run the snippet above on any stock EmulatorJS page.

Report `emu_fps` and `disp_fps` separately — if only the displayed frame rate drops it
is a paint problem, if the emulator frame count drops too the run loop is being starved.
Here both dropped together.

## Caveats

- My numbers come from headless Chromium on **software GL (SwiftShader)**, so the
  absolute values are not phone numbers. The **direction and ratio** held across every
  run, and the control experiment above rules out my own code.
- On a real Android phone the change is clearly noticeable to the user, but I have not
  instrumented it there. If anyone can run the snippet above on hardware, that would
  settle it.
- Context: found while building a single-file EmulatorJS front-end where the whole
  bottom half of the screen is touch controls, so the "finger is on the glass" case is
  the normal case rather than an edge case. That is probably why it showed up so
  starkly.
