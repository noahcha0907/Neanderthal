export type NodeKind = 'source' | 'concept' | 'artwork';
export type DocType = 'literary' | 'poem' | 'lyric' | 'philosophy' | 'history' | 'design' | 'user_upload' | string;

export interface GraphNode {
  id: string;
  kind: NodeKind;
  // source fields
  title?: string;
  author?: string;
  doc_type?: DocType;
  year?: number;
  chunk_index?: number;
  text?: string;
  // concept fields
  label?: string;
  // artwork fields
  artwork_id?: string;
  created_at?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: 'similarity' | 'concept' | 'influence';
  weight: number;
}

export interface GraphState {
  node_count: number;
  edge_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}
