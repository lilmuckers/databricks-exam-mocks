// Reference metadata loader.
// Fetches /references-meta.json once per page load and exposes it as
// window.REFS_META for use by renderReferenceCard() in utils.js.

let _loaded = false;
let _loading = null;

export async function loadRefsMeta() {
  if (_loaded) return;
  if (_loading) return _loading;
  _loading = (async () => {
    try {
      const res = await fetch('/references-meta.json');
      if (res.ok) window.REFS_META = await res.json();
    } catch {}
    _loaded = true;
  })();
  return _loading;
}
