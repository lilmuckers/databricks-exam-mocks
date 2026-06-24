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
      if (res.ok) {
        window.REFS_META = await res.json();
        console.debug('[refs] loaded', Object.keys(window.REFS_META).length, 'entries');
      } else {
        console.debug('[refs] references-meta.json not found (HTTP', res.status, ')— cards will use fallback titles only');
      }
    } catch (e) {
      console.debug('[refs] failed to load references-meta.json:', e.message);
    }
    _loaded = true;
  })();
  return _loading;
}
