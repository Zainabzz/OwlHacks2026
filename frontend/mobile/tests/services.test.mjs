import { test, after } from 'node:test';
import assert from 'node:assert/strict';

process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000/';
const { getRoutes } = await import('../src/services/routing.js');
const { suggestPlaces, retrievePlace, createSearchSession } = await import('../src/services/search.js');
const originalFetch = globalThis.fetch;
after(() => { globalThis.fetch = originalFetch; });
const start = { latitude: 39.9496, longitude: -75.1719 };
const end = { latitude: 39.9524, longitude: -75.1636 };
const route = { id: 'route-1', coordinates: [start, end], metrics: { temperatureC: 20 } };

 test('posts resolved coordinates to backend and preserves shared route metrics', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/api/routes');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { start, destination: end });
    return { ok: true, json: async () => ({ routes: [route] }) };
  };
  assert.deepEqual(await getRoutes(start, end), [route]);
});

test('handles validation, unreachable server, malformed payload, and no routes', async () => {
  await assert.rejects(getRoutes(null, end), /valid starting/);
  globalThis.fetch = async () => { throw new TypeError('network'); };
  await assert.rejects(getRoutes(start, end), /Cannot reach/);
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: 'Provider unavailable' }) });
  await assert.rejects(getRoutes(start, end), /Provider unavailable/);
  globalThis.fetch = async () => ({ ok: false, json: async () => { throw new SyntaxError(); } });
  await assert.rejects(getRoutes(start, end), /invalid response/);
  for (const routes of [null, [{ id: 'broken', coordinates: [] }], [route, route]]) {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ routes }) });
    await assert.rejects(getRoutes(start, end), /invalid route/);
  }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ routes: [] }) });
  await assert.rejects(getRoutes(start, end), /No walking routes/);
});

test('search resolves a selection through a separate retrieval call using the same session', async () => {
  const token = createSearchSession();
  assert.match(token, /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
  globalThis.fetch = async url => {
    const parsed = new URL(url);
    assert.equal(parsed.searchParams.get('session_token'), token);
    return { ok: true, json: async () => parsed.pathname.endsWith('suggest')
      ? { suggestions: [{ id: 'place:1', name: 'Market' }] }
      : { location: { ...end, name: 'Market' } } };
  };
  const results = await suggestPlaces('Market', token, start);
  assert.deepEqual(await retrievePlace(results[0].id, token), { ...end, name: 'Market' });
});
