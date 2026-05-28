import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';

const sourceDir = 'data';
const targetDir = join('dist', 'data');

await rm(targetDir, { recursive: true, force: true });
await mkdir(targetDir, { recursive: true });

const entries = await readdir(sourceDir, { withFileTypes: true });
await Promise.all(
  entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .map((entry) => cp(join(sourceDir, entry.name), join(targetDir, entry.name))),
);

console.log(`Copied data snapshots to ${targetDir}`);
