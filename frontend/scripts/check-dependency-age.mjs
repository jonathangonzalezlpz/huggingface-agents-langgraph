#!/usr/bin/env node
/**
 * Fails when any locked dependency version was published less than N days ago.
 * Recently published versions are the main window for compromised releases, so new
 * versions are adopted only after a cooling-off period (default 14 days).
 *
 * Usage: node scripts/check-dependency-age.mjs [--days 14]
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const REGISTRY = 'https://registry.npmjs.org';
const CONCURRENCY = 8;
const DAY_MS = 24 * 60 * 60 * 1000;

const daysFlag = process.argv.indexOf('--days');
const minimumDays = daysFlag === -1 ? 14 : Number(process.argv[daysFlag + 1]);
if (!Number.isFinite(minimumDays) || minimumDays < 0) {
  console.error('--days must be a non-negative number');
  process.exit(2);
}

const lock = JSON.parse(readFileSync(join(import.meta.dirname, '..', 'package-lock.json'), 'utf8'));

/** Distinct name@version pairs that come from the public registry. */
const entries = new Map();
for (const [path, info] of Object.entries(lock.packages)) {
  if (path === '' || !info.version || !info.resolved?.startsWith(`${REGISTRY}/`)) continue;
  const name = path.split('node_modules/').pop();
  entries.set(`${name}@${info.version}`, { name, version: info.version });
}

async function publishedAt({ name, version }) {
  const url = `${REGISTRY}/${name.replace('/', '%2F')}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${name}: registry responded ${response.status}`);
  const packument = await response.json();
  const published = packument.time?.[version];
  if (!published) throw new Error(`${name}@${version}: no publish date in the registry`);
  return new Date(published);
}

const queue = [...entries.values()];
const now = Date.now();
const tooNew = [];
const failures = [];

async function worker() {
  for (let entry = queue.shift(); entry; entry = queue.shift()) {
    try {
      const date = await publishedAt(entry);
      const ageDays = (now - date.getTime()) / DAY_MS;
      if (ageDays < minimumDays) tooNew.push({ ...entry, date, ageDays });
    } catch (error) {
      failures.push(error instanceof Error ? error.message : String(error));
    }
  }
}

await Promise.all(Array.from({ length: CONCURRENCY }, worker));

console.log(`Checked ${entries.size} package versions against a ${minimumDays}-day minimum age.`);
for (const item of tooNew.sort((a, b) => a.ageDays - b.ageDays)) {
  console.log(
    `  TOO NEW  ${item.name}@${item.version}  published ${item.date.toISOString().slice(0, 10)} (${item.ageDays.toFixed(1)} days)`,
  );
}
for (const message of failures) console.log(`  COULD NOT CHECK  ${message}`);

if (tooNew.length > 0 || failures.length > 0) {
  console.log(`\nResult: ${tooNew.length} too new, ${failures.length} unchecked.`);
  process.exit(1);
}
console.log('Result: every version is old enough.');
