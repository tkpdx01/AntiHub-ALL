import assert from 'node:assert/strict';

import { createGeminiSseParser } from '../src/api/gemini_sse_parser.js';

const events = [];
const parser = createGeminiSseParser((event) => events.push(event));

const payload = {
  response: {
    candidates: [
      {
        content: {
          parts: [{ text: 'hello' }]
        }
      }
    ]
  }
};

const line = `data: ${JSON.stringify(payload)}\n`;

// Simulate upstream chunking that splits a single JSON line into two pieces.
// Old implementation (`chunk.split('\\n')`) would parse the first half (no newline) as JSON and fail,
// then ignore the second half (not starting with "data:"), dropping the event.
const splitAt = Math.floor(line.length / 2);
parser.feed(line.slice(0, splitAt));
parser.feed(line.slice(splitAt));
parser.flush();

assert.equal(events.length, 1);
assert.deepEqual(events[0], { type: 'text', content: 'hello' });

console.log('PASS gemini_sse_parser.test.js');
