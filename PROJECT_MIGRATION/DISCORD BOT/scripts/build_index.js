/*
  build_index.js
  Small script to run KB indexing using functions exported from ask.js.
  Usage:
    node scripts/build_index.js
  Make sure environment variables are set (HUGGINGFACE_API_TOKEN if you want HF embeddings).
*/

const path = require('path');

(async () => {
  try {
    const ask = require(path.join(__dirname, '..', 'ask.js'));
  } catch (err) {
    console.error('Failed to load ask.js:', err.message);
    process.exit(1);
  }

  const askModule = require(path.join(__dirname, '..', 'ask.js'));
  const internals = askModule._internal;
  if (!internals) {
    console.error('ask.js does not export _internal. Aborting.');
    process.exit(1);
  }

  try {
    console.log('Starting KB indexing (this may take a while on first run)...');
    const idx = await internals.indexKnowledgeBase({ forceReindex: true });
    console.log('Indexing complete. Items indexed:', idx.length);
    process.exit(0);
  } catch (err) {
    console.error('Indexing failed:', err.message);
    process.exit(1);
  }
})();
