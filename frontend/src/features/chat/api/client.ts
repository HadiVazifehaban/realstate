import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import { getActiveWorkspaceId, getWorkspaceHeaderOverride } from '@/features/network/api/client';
import type { Conversation, Message } from '../utils/types';

type ApiMessage = {
  id: string; sequence: number; sender_subject: string; sender_name: string;
  client_message_id: string; body: string; created_at: string;
};
type ApiConversation = {
  id: string; title: string; created_by_subject: string; created_at: string;
  members: Array<{ subject: string; display_name: string }>;
  last_message: ApiMessage | null;
};

const mapMessage = (row: ApiMessage): Message => ({
  id: row.id, sequence: row.sequence, senderSubject: row.sender_subject,
  senderName: row.sender_name, clientMessageId: row.client_message_id,
  body: row.body, createdAt: row.created_at
});

const mapConversation = (row: ApiConversation): Conversation => ({
  id: row.id, title: row.title, createdBySubject: row.created_by_subject,
  createdAt: row.created_at,
  members: row.members.map((member) => ({ subject: member.subject, displayName: member.display_name })),
  lastMessage: row.last_message ? mapMessage(row.last_message) : null
});

export class ChatApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
    this.name = 'ChatApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  const selectedWorkspace = getWorkspaceHeaderOverride() === undefined
    ? getActiveWorkspaceId()
    : getWorkspaceHeaderOverride() ?? null;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store', ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(selectedWorkspace ? { 'X-Workspace-ID': selectedWorkspace } : {}),
        ...options.headers
      }
    });
  } catch (error) {
    throw new ChatApiError(0, 'network_unreachable', networkFailureMessage(error));
  }
  if (!response.ok) {
    let code = 'request_failed';
    let message = response.statusText || 'درخواست چت ناموفق بود.';
    try {
      const body = (await response.json()) as {
        detail?: { error?: string; message?: string } | string;
      };
      code = typeof body.detail === 'string' ? code : body.detail?.error ?? code;
      message = typeof body.detail === 'string' ? body.detail : body.detail?.message ?? message;
    } catch {
      // Keep the HTTP fallback for non-JSON intermediary responses.
    }
    throw new ChatApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export async function fetchConversations(): Promise<Conversation[]> {
  return (await request<ApiConversation[]>('/chat/conversations')).map(mapConversation);
}

export async function fetchMessages(conversationId: string): Promise<Message[]> {
  const rows = await request<ApiMessage[]>(`/chat/conversations/${encodeURIComponent(conversationId)}/messages`);
  return rows.map(mapMessage);
}

export async function sendMessage(conversationId: string, body: string, clientMessageId: string): Promise<Message> {
  const row = await request<ApiMessage>(`/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: 'POST', body: JSON.stringify({ body, client_message_id: clientMessageId })
  });
  return mapMessage(row);
}