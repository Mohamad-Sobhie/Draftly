#!/usr/bin/env node
// Create or update a Draftly thesis folder.
//
//   npx create-draftly my-thesis            new folder (or add Draftly to an existing one)
//   npx create-draftly my-thesis --update   refresh skill, scripts and settings; keeps the student's work
//   npx create-draftly my-thesis --no-setup copy files only, skip the Python setup
//
// Without publishing: npx github:Mohamad-Sobhie/Draftly my-thesis
'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const PKG_ROOT = path.resolve(__dirname, '..');

// npm never ships .gitignore files, so it lives here. scripts/selftest.py checks it matches the repo's.
const GITIGNORE = `# --- The student's private material: never in the template repo ---
references/pdf/*
references/text/*
references/inbox/*
references/bibliography.md
notes/*
sessions/*
drafts/*
My Thesis Drafts/*
thesis-brief.md
library.html
!references/pdf/.gitkeep
!references/text/.gitkeep
!references/inbox/.gitkeep
!notes/.gitkeep
!sessions/.gitkeep
!drafts/.gitkeep
!My Thesis Drafts/.gitkeep

# --- Local tooling ---
.venv/
__pycache__/
*.pyc
.claude/settings.local.json
.DS_Store
Thumbs.db
`;

// Template files that --update may replace. Everything else (library, notes, drafts, brief) is the student's.
const UPDATABLE = [/^\.claude\/skills\/draftly\//, /^\.claude\/settings\.json$/, /^scripts\//, /^CLAUDE\.md$/, /^README\.md$/];
const SKIP = [/^bin\//, /^package\.json$/, /^node_modules\//, /^\.git\//, /^\.venv\//, /__pycache__/, /\.pyc$/,
  /^\.claude\/settings\.local\.json$/, /^library\.html$/, /^thesis-brief\.md$/, /^\.DS_Store$/];
// Private content that may sit in a checkout of the template: only the empty placeholders are copied.
const PRIVATE_FILE = /^(references\/(pdf|text|inbox)|notes|sessions|drafts|My Thesis Drafts)\/(?!\.gitkeep$)|^references\/bibliography\.md$/;

const c = process.stdout.isTTY ? { b: '\x1b[1m', g: '\x1b[32m', y: '\x1b[33m', r: '\x1b[31m', d: '\x1b[2m', x: '\x1b[0m' }
  : { b: '', g: '', y: '', r: '', d: '', x: '' };
const ok = (m) => console.log(`  ${c.g}✓${c.x} ${m}`);
const warn = (m) => console.log(`  ${c.y}!${c.x} ${m}`);
const die = (m) => { console.error(`  ${c.r}✗${c.x} ${m}`); process.exit(1); };

function usage() {
  console.log(`${c.b}create-draftly${c.x} - set up a Draftly thesis folder for Claude

Usage:
  npx create-draftly [folder]            create a new thesis folder (default: my-thesis),
                                         or add Draftly to an existing folder without touching its files
  npx create-draftly [folder] --update   refresh the skill, scripts and settings in a Draftly folder;
                                         the library, notes, drafts and thesis brief are never touched
  npx create-draftly [folder] --no-setup copy the files but skip the Python setup

After setup: open the folder in the Claude app (Code), trust it, and type: menu`);
}

function walk(dir, base = dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    const rel = path.relative(base, full).split(path.sep).join('/');
    if (SKIP.some((rx) => rx.test(rel + (e.isDirectory() ? '/' : '')))) continue;
    if (e.isDirectory()) walk(full, base, out);
    else if (!PRIVATE_FILE.test(rel)) out.push(rel);
  }
  return out;
}

function copy(rel, target, overwrite) {
  const src = path.join(PKG_ROOT, rel);
  const dst = path.join(target, rel);
  if (fs.existsSync(dst) && !overwrite) return 'kept';
  const existed = fs.existsSync(dst);
  if (existed && fs.readFileSync(src).equals(fs.readFileSync(dst))) return 'same';
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  if (/^scripts\/.*\.(py|sh)$/.test(rel)) fs.chmodSync(dst, 0o755);
  return existed ? 'updated' : 'added';
}

function has(cmd, args = ['--version']) {
  const r = spawnSync(cmd, args, { stdio: 'ignore', shell: process.platform === 'win32' });
  return r.status === 0;
}

function findPython() {
  const cands = process.platform === 'win32' ? [['py', ['-3']], ['python', []], ['python3', []]]
    : [['python3', []], ['python', []]];
  for (const [cmd, pre] of cands) {
    const r = spawnSync(cmd, [...pre, '-c', 'import sys; print(sys.version_info >= (3, 10))'],
      { encoding: 'utf8', shell: process.platform === 'win32' });
    if (r.status === 0 && r.stdout.trim() === 'True') return [cmd, pre];
  }
  return null;
}

// Windows without bash: same steps as scripts/setup.sh.
function nodeSetup(target) {
  const py = findPython();
  if (!py) die('Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run this again.');
  const run = (cmd, args, label) => {
    const r = spawnSync(cmd, args, { cwd: target, stdio: 'inherit', shell: process.platform === 'win32' });
    if (r.status !== 0) die(`${label} failed - see the messages above.`);
  };
  const vpy = path.join(target, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  if (!fs.existsSync(vpy)) run(py[0], [...py[1], '-m', 'venv', '.venv'], 'Creating the Python environment');
  run(vpy, ['-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'], 'Updating pip');
  run(vpy, ['-m', 'pip', 'install', '--quiet', '-r', 'scripts/requirements.txt'], 'Installing Python packages');
  ok('Python packages installed in .venv');
  if (!has('pdftotext', ['-v'])) warn('poppler not found (optional, better PDF text): winget install oschwartz10612.Poppler');
  if (!has('tesseract')) warn('tesseract not found (optional, scanned PDFs): winget install UB-Mannheim.TesseractOCR');
  run(vpy, ['scripts/selftest.py'], 'Self-test');
  run(vpy, ['scripts/build_library.py'], 'Building library.html');
}

function setup(target) {
  console.log(`\n${c.b}Setting up the helper tools${c.x}`);
  const bash = process.platform !== 'win32' || has('bash');
  if (bash) {
    const r = spawnSync('bash', ['scripts/setup.sh'], { cwd: target, stdio: 'inherit',
      env: { ...process.env, DRAFTLY_INSTALLER: '1' } });
    if (r.status !== 0) die('Setup failed - see the messages above.');
  } else {
    nodeSetup(target);
  }
}

function main() {
  const args = process.argv.slice(2);
  if (args.includes('-h') || args.includes('--help')) return usage();
  const update = args.includes('--update');
  const skipSetup = args.includes('--no-setup');
  const unknown = args.filter((a) => a.startsWith('-') && !['--update', '--no-setup'].includes(a));
  if (unknown.length) { usage(); die(`Unknown option: ${unknown.join(' ')}`); }
  const folder = args.find((a) => !a.startsWith('-')) || 'my-thesis';
  const target = path.resolve(process.cwd(), folder);
  const isDraftly = fs.existsSync(path.join(target, '.claude', 'skills', 'draftly', 'SKILL.md'));
  const version = JSON.parse(fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8')).version;

  console.log(`${c.b}Draftly ${version}${c.x} ${c.d}→ ${target}${c.x}`);
  if (path.resolve(target) === PKG_ROOT) die('That is the Draftly template itself. Choose another folder.');
  if (update && !isDraftly) die('That folder is not a Draftly thesis folder yet. Run without --update to create it.');
  if (!update && isDraftly) die(`That folder already has Draftly. To refresh it: npx create-draftly "${folder}" --update`);
  if (fs.existsSync(target) && !fs.statSync(target).isDirectory()) die('That path is a file, not a folder.');

  const files = walk(PKG_ROOT);
  const tally = { added: 0, updated: 0, kept: 0, same: 0 };
  for (const rel of files) {
    if (update && !UPDATABLE.some((rx) => rx.test(rel))) continue;
    tally[copy(rel, target, update)]++;
  }
  const gi = path.join(target, '.gitignore');
  if (!fs.existsSync(gi)) { fs.writeFileSync(gi, GITIGNORE); tally.added++; }

  if (update) {
    ok(`Updated ${tally.updated} file(s), ${tally.added} new, ${tally.same} unchanged. Library, notes, drafts and brief untouched.`);
  } else {
    ok(`Added ${tally.added} file(s)` + (tally.kept ? `, kept ${tally.kept} existing file(s) unchanged` : ''));
  }

  if (skipSetup) {
    warn('Skipped setup. Before first use run: bash scripts/setup.sh (inside the folder)');
  } else {
    setup(target);
  }

  console.log(`\n${c.b}Next:${c.x} open ${c.b}${folder}${c.x} in the Claude app (Code tab), accept "trust this folder", and type ${c.b}menu${c.x}.`);
  if (!update) console.log(`${c.d}Tip: put the student's own files (abstract, reading list) in the folder, and source PDFs in references/inbox.${c.x}`);
}

main();
