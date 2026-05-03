/*
  inspect_kb.js
  Lightweight script to inspect the `data/wos` knowledge base files and show counts of paragraphs.
  Does NOT load embeddings or heavy libs, safe for quick checks.
*/

const fs = require('fs');
const path = require('path');

const KB_DIR = path.join(__dirname, '..', 'data', 'wos');

function inspectKB() {
  if (!fs.existsSync(KB_DIR)) {
    console.log(`KB dir not found at ${KB_DIR}`);
    return;
  }

  const files = fs.readdirSync(KB_DIR).filter(f => f.toLowerCase().endsWith('.txt'));
  if (files.length === 0) {
    console.log('No .txt files found in KB dir:', KB_DIR);
    return;
  }

  let totalParas = 0;
  console.log('Found KB files:');
  for (const file of files) {
    const fp = path.join(KB_DIR, file);
    const raw = fs.readFileSync(fp, 'utf8');
    const paragraphs = raw.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
    totalParas += paragraphs.length;
    console.log(` - ${file}: ${paragraphs.length} paragraphs`);
  }
  console.log(`Total paragraphs across all files: ${totalParas}`);
}

inspectKB();
