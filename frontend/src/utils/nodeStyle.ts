import type { DocType, NodeKind } from '../types/graph';

// Hex colors for node kinds / doc types
const DOC_TYPE_COLORS: Record<string, number> = {
  literary:    0x93c5fd, // light blue-300
  poem:        0xec4899, // pink
  lyric:       0xf43f5e, // rose
  philosophy:  0xbfdbfe, // light blue-200
  history:     0xf59e0b, // amber
  design:      0x10b981, // emerald
  user_upload: 0x06b6d4, // cyan
};

const KIND_COLORS: Record<NodeKind, number> = {
  source:  0x93c5fd, // light blue-300 (fallback)
  concept: 0xe2e8f0, // light slate
  artwork: 0xfef08a, // light yellow-200
};

export function nodeColor(kind: NodeKind, doc_type?: DocType): number {
  if (kind === 'source' && doc_type && doc_type in DOC_TYPE_COLORS) {
    return DOC_TYPE_COLORS[doc_type];
  }
  return KIND_COLORS[kind];
}

export function nodeColorHex(kind: NodeKind, doc_type?: DocType): string {
  return '#' + nodeColor(kind, doc_type).toString(16).padStart(6, '0');
}
