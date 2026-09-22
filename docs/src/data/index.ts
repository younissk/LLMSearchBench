import type {Release} from './types';
import v010 from './releases/v0.1.0.json';

/**
 * Benchmark data is versioned independently of the docs pages: cutting a docs
 * version (`npm run version:cut`) freezes the prose, adding a file here freezes
 * the numbers. A page always names the release it renders.
 */
export const releases: Record<string, Release> = {
  'v0.1.0': v010 as Release,
};

export const LATEST = 'v0.1.0';

export function getRelease(version: string = LATEST): Release {
  const release = releases[version];
  if (!release) {
    throw new Error(
      `Unknown benchmark release "${version}". Known: ${Object.keys(releases).join(', ')}`,
    );
  }
  return release;
}

export const releaseVersions = Object.keys(releases).sort().reverse();

export type {Release, ResultRow} from './types';
