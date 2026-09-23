import React from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import clsx from 'clsx';
import styles from './VendorIcon.module.css';
import sources from '@site/static/img/vendors/sources.json';

interface Vendor {
  /** How the vendor writes its own name. */
  name: string;
  /** One or two letters, drawn in the badge. */
  mark: string;
  /** Badge colour. Each one carries white text at 4.5:1 or better. */
  color: string;
}

/**
 * Keyed by the namespace of a model id, which is how every provider we use
 * spells the vendor: `deepseek/deepseek-r1` -> `deepseek`.
 *
 * The colour and letters here are the fallback, used when a vendor has no logo
 * file. Where one exists it wins — see `sources.json`, which records where each
 * mark came from and when.
 */
const VENDORS: Record<string, Vendor> = {
  openai: {name: 'OpenAI', mark: 'OA', color: '#0b7a62'},
  qwen: {name: 'Qwen (Alibaba)', mark: 'Q', color: '#6242d6'},
  deepseek: {name: 'DeepSeek', mark: 'DS', color: '#3a55c9'},
  'z-ai': {name: 'Z.ai (Zhipu)', mark: 'Z', color: '#2160b8'},
  moonshot: {name: 'Moonshot AI (Kimi)', mark: 'K', color: '#1f2937'},
  'meta-llama': {name: 'Meta', mark: 'Me', color: '#1257c4'},
  mistralai: {name: 'Mistral AI', mark: 'MS', color: '#b4460f'},
  nvidia: {name: 'NVIDIA', mark: 'NV', color: '#4a7a0b'},
  minimax: {name: 'MiniMax', mark: 'MM', color: '#a93226'},
  xiaomi: {name: 'Xiaomi', mark: 'Mi', color: '#c2410c'},
  thinkingmachines: {name: 'Thinking Machines', mark: 'TM', color: '#374151'},
  meituan: {name: 'Meituan', mark: 'MT', color: '#8a6d00'},
  tencent: {name: 'Tencent', mark: 'T', color: '#0e7490'},
  avey: {name: 'Avey', mark: 'AV', color: '#4d7c0f'},
  anthropic: {name: 'Anthropic', mark: 'A', color: '#b04a26'},
};

const UNKNOWN: Vendor = {name: 'Unknown vendor', mark: '?', color: '#6b7280'};

/** The vendor namespace of a model id. */
export function vendorKey(modelId: string): string {
  return modelId.split('/')[0].toLowerCase();
}

export function vendorName(modelId: string): string {
  return (VENDORS[vendorKey(modelId)] ?? UNKNOWN).name;
}

export interface VendorIconProps {
  /** Full model id, e.g. `deepseek/deepseek-r1`. */
  model: string;
  size?: number;
}

/**
 * A small badge for the vendor behind a model.
 *
 * Decorative: the model name sits next to it in every place it is used, so it
 * is hidden from screen readers rather than repeating that name.
 */
export default function VendorIcon({model, size = 18}: VendorIconProps) {
  const key = vendorKey(model);
  const vendor = VENDORS[key] ?? UNKNOWN;
  const logo = (sources as Record<string, {file: string} | undefined>)[key];
  const src = useBaseUrl(`/img/vendors/${logo?.file ?? ''}`);

  if (logo) {
    // Most of these marks are single-colour black, which disappears on the
    // dark surface — so each one sits on its own light chip rather than
    // directly on the page.
    return (
      <span
        className={clsx(styles.badge, styles.chip)}
        style={{width: size, height: size}}
        title={vendor.name}
        aria-hidden="true"
      >
        <img className={styles.logo} src={src} alt="" />
      </span>
    );
  }

  return (
    <span
      className={styles.badge}
      style={{
        background: vendor.color,
        width: size,
        height: size,
        fontSize: size * (vendor.mark.length > 1 ? 0.42 : 0.55),
      }}
      title={vendor.name}
      aria-hidden="true"
    >
      {vendor.mark}
    </span>
  );
}
