// The simulator on GitHub Pages, where there is no simulator.py to talk to.
//
// Pyodide runs the same Python in the browser - main.py's loop, nd_timer, and
// simulator.py's own request routing - so the page asks it exactly what it
// would have asked the server. scripts/build-simulator-page.py puts this in
// front of simulator.html; run locally, the page never loads it.

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/';

// Run once the code is unpacked. Two things the browser lacks are stood in for
// here rather than in simulator.py, because only this copy needs them. There
// are no threads, and the timed capture main.py hands to one returns at once
// with a fake camera anyway, so it simply runs inline. And there is no fcntl,
// which nd_timer.battery imports only to read the UPS over I2C - something the
// simulator never does, since it sets the gauge by hand.
const BOOT = `
import sys
import threading
import types

class _Inline(threading.Thread):
    def start(self):
        self.run()

threading.Thread = _Inline
sys.modules["fcntl"] = types.ModuleType("fcntl")
sys.path.insert(0, "/device/scripts")

from simulator import Simulator, answered

_simulator = Simulator(speed=60.0)

def ask(method, path):
    body, _ = answered(_simulator, method, path)
    return body.decode()

def frame():
    body, _ = answered(_simulator, "GET", "/frame.png")
    return body

(ask, frame)
`;

function say(text) {
  let note = document.getElementById('loading');
  if (!note) {
    note = document.createElement('p');
    note.id = 'loading';
    note.className = 'keys';
    document.querySelector('h1').after(note);
  }
  note.textContent = text;
}

const started = (async () => {
  say('Starting Python in the browser…');
  const { loadPyodide } = await import(PYODIDE + 'pyodide.mjs');
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  await pyodide.loadPackage('pillow');
  const code = await (await fetch('device.zip')).arrayBuffer();
  pyodide.unpackArchive(code, 'zip', { extractDir: '/device' });
  const [ask, frame] = pyodide.runPython(BOOT).toJs();
  document.getElementById('loading').remove();
  return { ask, frame };
})();

started.catch((error) => say(`Could not start the simulator: ${error}`));

let shown = null;

window.simulatedDevice = {
  ask: async (method, path) => JSON.parse((await started).ask(method, path)),
  frame: async () => {
    const png = (await started).frame();
    const bytes = png.toJs();
    png.destroy();
    // Each frame is a new object URL; the one it replaces would otherwise be
    // held for as long as the tab is open, at two or three a second.
    if (shown) URL.revokeObjectURL(shown);
    shown = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    return shown;
  },
};
