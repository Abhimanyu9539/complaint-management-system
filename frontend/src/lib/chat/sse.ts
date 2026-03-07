import type { ChatEvent } from './types';

interface RawRecord {
  event: string | null;
  data: string;
}

function parseRecord(block: string): RawRecord {
  let event: string | null = null;
  const dataLines: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue; // blank / comment (e.g. keep-alive ping)
    const idx = rawLine.indexOf(':');
    const field = idx === -1 ? rawLine : rawLine.slice(0, idx);
    const value = idx === -1 ? '' : rawLine.slice(idx + 1).trimStart();
    if (field === 'event') event = value;
    else if (field === 'data') dataLines.push(value);
  }

  return { event, data: dataLines.join('\n') };
}

function toChatEvent(record: RawRecord): ChatEvent | null {
  if (!record.event || !record.data) return null;

  switch (record.event) {
    case 'token': {
      try {
        const parsed = JSON.parse(record.data);
        const text = typeof parsed === 'string' ? parsed : (parsed?.text ?? '');
        return { type: 'token', text: String(text) };
      } catch {
        return { type: 'token', text: record.data };
      }
    }
    case 'citations': {
      try {
        const citations = JSON.parse(record.data);
        return { type: 'citations', citations: Array.isArray(citations) ? citations : [] };
      } catch {
        return { type: 'error', message: 'Malformed citations payload from server.' };
      }
    }
    case 'done': {
      try {
        const parsed = JSON.parse(record.data);
        return {
          type: 'done',
          message_id: parsed.message_id,
          langsmith_run_id: parsed.langsmith_run_id ?? null,
          session_id: parsed.session_id,
        };
      } catch {
        return { type: 'error', message: 'Malformed done payload from server.' };
      }
    }
    case 'error': {
      try {
        const parsed = JSON.parse(record.data);
        return { type: 'error', message: parsed?.message ?? record.data };
      } catch {
        return { type: 'error', message: record.data };
      }
    }
    default:
      return null; // unknown event name — ignore
  }
}

/**
 * Consumes a fetch response body as newline-delimited SSE records and yields
 * typed ChatEvents. Records are separated by a blank line; each may have an
 * `event:` line and one or more `data:` lines (joined with `\n`).
 */
export async function* parseSSEStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex: number;
      while ((sepIndex = buffer.search(/\r?\n\r?\n/)) !== -1) {
        const block = buffer.slice(0, sepIndex);
        const match = buffer.slice(sepIndex).match(/^\r?\n\r?\n/);
        buffer = buffer.slice(sepIndex + (match?.[0].length ?? 2));

        const record = parseRecord(block);
        const event = toChatEvent(record);
        if (event) yield event;
        if (event?.type === 'error') return;
      }
    }

    // flush any trailing record without a final blank-line separator
    buffer += decoder.decode();
    if (buffer.trim()) {
      const event = toChatEvent(parseRecord(buffer));
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
