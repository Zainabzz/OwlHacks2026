import { test, after } from 'node:test';
import assert from 'node:assert/strict';

process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000/';
const { getRoutes } = await import('../src/services/routing.js');
const { suggestPlaces, retrievePlace, createSearchSession } = await import('../src/services/search.js');
const { formatDuration } = await import('../src/services/formatting.js');
const originalFetch = globalThis.fetch;
after(() => { globalThis.fetch = originalFetch; });
const start = { latitude: 39.9496, longitude: -75.1719 };
const end = { latitude: 39.9524, longitude: -75.1636 };
const route = { id: 'route-1', coordinates: [start, end], metrics: { temperatureC: 20 } };

test('formats route times as minutes or hours and minutes', () => {
  assert.equal(formatDuration(59), '59 min');
  assert.equal(formatDuration(60), '1 hr');
  assert.equal(formatDuration(61.4), '1 hr 1 min');
  assert.equal(formatDuration(125), '2 hrs 5 min');
  assert.equal(formatDuration(null), 'Not available');
});

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

test('weather uses backend coordinates and preserves both provider statuses', async () => {
  const { fetchWeather } = await import('../src/services/weather.js');
  const data = { status: 'ok', source: 'openMeteo', providers: {
    openMeteo: { status: 'ok', data: { temperatureC: 20 } },
    openWeather: { status: 'unavailable', error: 'API key rejected' },
  } };
  globalThis.fetch = async url => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, '/api/weather');
    assert.equal(parsed.searchParams.get('latitude'), String(start.latitude));
    assert.equal(parsed.searchParams.get('longitude'), String(start.longitude));
    assert.equal(parsed.searchParams.has('appid'), false);
    return { ok: true, json: async () => data };
  };
  assert.deepEqual(await fetchWeather(start.latitude, start.longitude), data);
  await assert.rejects(fetchWeather(91, 0), /valid location/);
  globalThis.fetch = async () => ({ ok: true, json: async () => ({}) });
  await assert.rejects(fetchWeather(start.latitude, start.longitude), /invalid weather/);
});


test('coordinate searches resolve locally and reject invalid coordinate input', async () => {
  const { parseCoordinateLocation } = await import('../src/services/search.js');
  globalThis.fetch = async () => { throw new Error('Coordinates should not call a provider'); };
  const [result] = await suggestPlaces(' 39.95, -75.16 ', createSearchSession());
  assert.deepEqual(result.location, { latitude: 39.95, longitude: -75.16, name: '39.95, -75.16' });
  for (const query of ['91, 0', '0, -181', ', 0', '0,', '0x10, 0', 'Market, Philadelphia', '1, 2, 3']) {
    assert.equal(parseCoordinateLocation(query), null);
  }
  assert.equal(parseCoordinateLocation('0, 0').latitude, 0);
});

test('supports top 3 ranked routes with preferred and alternative designations', async () => {
  const routes = [
    { id: 'route-1', name: 'Route 1', isPreferred: true, rank: 1, coordinates: [start, end], metrics: { durationMinutes: 10 } },
    { id: 'route-2', name: 'Route 2', isPreferred: false, rank: 2, coordinates: [start, end], metrics: { durationMinutes: 12 } },
    { id: 'route-3', name: 'Route 3', isPreferred: false, rank: 3, coordinates: [start, end], metrics: { durationMinutes: 14 } },
  ];
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ routes }) });
  const result = await getRoutes(start, end);
  assert.equal(result.length, 3);
  assert.equal(result[0].isPreferred, true);
  assert.equal(result[1].isPreferred, false);
  assert.equal(result[2].isPreferred, false);
  assert.equal(result[0].rank, 1);
  assert.equal(result[1].rank, 2);
  assert.equal(result[2].rank, 3);
});


test('ranked routes retain distinct Fahrenheit averages and exposure data', async () => {
  const routes = [1, 2, 3].map(rank => ({
    id: `route-${rank}`, rank, isPreferred: rank === 1, coordinates: [start, end],
    metrics: { temperatureF: 70 + rank, sunExposurePercent: rank * 10, rainExposurePercent: rank * 20, windImpact: rank },
    weather: { temperatureF: 70 + rank, coveragePercent: 100 },
    exposure: { sunBasis: 'open-sky', status: 'ok' },
  }));
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ routes }) });
  assert.deepEqual(await getRoutes(start, end), routes);
});
