#!/usr/bin/env node
// Установка русской локализации dsh-pet (оверлей файлов).
// Проверяет версию плагина по sha256, делает бэкап, копирует переводы и
// переименовывает ассеты (имена видео/мемов = id анимаций в конфиге).
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(here, 'manifest.json'), 'utf8'));
const renames = JSON.parse(readFileSync(join(here, 'renames.json'), 'utf8'));
const VERSION = manifest.upstream.version;
const args = process.argv.slice(2);

function fail(msg, code = 1) {
  console.error(`\nОШИБКА: ${msg}\n`);
  process.exit(code);
}
function sha(p) {
  return createHash('sha256').update(readFileSync(p)).digest('hex');
}
function flag(name) {
  const i = args.indexOf(name);
  return i === -1 ? null : args[i + 1] ?? true;
}

if (args.includes('--help') || args.includes('-h')) {
  console.log(`Установка русской локализации dsh-pet ${VERSION}

  node install.mjs                 найти плагин автоматически и установить
  node install.mjs --dir <путь>    указать папку плагина вручную
  node install.mjs --dry-run       только показать план, ничего не менять
  node install.mjs --restore <бэкап>  откатить установку

Папка плагина: <ДОМ>/.dsh/profiles/<профиль>/node_modules/dsh-pet`);
  process.exit(0);
}

// ---------- откат ----------
const restoreDir = flag('--restore');
if (restoreDir) {
  const info = JSON.parse(readFileSync(join(restoreDir, 'backup.json'), 'utf8'));
  const dir = info.pluginDir;
  if (!existsSync(dir)) fail(`папка плагина из бэкапа не найдена: ${dir}`);
  for (const rel of info.files) {
    const src = join(restoreDir, 'files', rel);
    const dst = join(dir, rel);
    if (!existsSync(src)) fail(`в бэкапе нет файла ${rel}`);
    copyFileSync(src, dst);
  }
  let back = 0;
  for (const r of info.renames.slice().reverse()) {
    const from = join(dir, r.from);
    const to = join(dir, r.to);
    if (existsSync(to) && !existsSync(from)) {
      renameSync(to, from);
      back++;
    }
  }
  console.log(`Откат выполнен: файлов ${info.files.length}, имён возвращено ${back}.`);
  console.log('Перезапустите DSH, чтобы изменения вступили в силу.');
  process.exit(0);
}

// ---------- поиск плагина ----------
function autoDetect() {
  const root = join(homedir(), '.dsh', 'profiles');
  if (!existsSync(root)) return [];
  return readdirSync(root)
    .map((p) => join(root, p, 'node_modules', 'dsh-pet'))
    .filter((p) => existsSync(join(p, 'package.json')));
}
let dir = flag('--dir');
if (!dir) {
  const found = autoDetect();
  if (found.length === 0) fail('dsh-pet не найден. Сначала установите плагин, затем повторите.');
  if (found.length > 1) fail(`найдено несколько установок, укажите нужную через --dir:\n  ${found.join('\n  ')}`);
  dir = found[0];
}
if (!existsSync(join(dir, 'package.json'))) fail(`в ${dir} нет package.json — это не папка dsh-pet.`);

// ---------- проверка версии ----------
const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'));
if (pkg.name !== 'dsh-pet') fail(`в ${dir} установлен не dsh-pet (name=${pkg.name}).`);
if (pkg.version !== VERSION) {
  fail(
    `оверлей собран для dsh-pet ${VERSION}, у вас ${pkg.version}.\n` +
      `Обновите репозиторий под свою версию либо поставьте dsh-pet@${VERSION}.\n` +
      `Ничего не изменено.`,
  );
}

// ---------- проверка хешей ----------
const clean = [];
const patched = [];
const unknown = [];
for (const f of manifest.files) {
  const p = join(dir, f.path);
  if (!existsSync(p)) {
    unknown.push(`${f.path} (файла нет)`);
    continue;
  }
  const h = sha(p);
  if (h === f.before) clean.push(f.path);
  else if (h === f.after) patched.push(f.path);
  else unknown.push(f.path);
}
if (unknown.length) {
  fail(
    `файлы плагина отличаются от dsh-pet ${VERSION}:\n  ${unknown.join('\n  ')}\n` +
      `Похоже, установлена другая версия или файлы уже правили. Ничего не изменено.`,
  );
}
const already = patched.length === manifest.files.length;
if (already && !args.includes('--dry-run')) console.log('Файлы уже переведены; проверяю только имена ассетов.');

// ---------- план по ассетам ----------
const todoRenames = [];
let alreadyRenamed = 0;
for (const r of renames) {
  const from = join(dir, r.from);
  const to = join(dir, r.to);
  if (existsSync(from)) todoRenames.push(r);
  else if (existsSync(to)) alreadyRenamed++;
  else fail(`ассет не найден: ${r.from} — папка плагина неполная.`);
}

if (args.includes('--dry-run')) {
  console.log(`План: скопировать ${already ? 0 : clean.length} файлов, переименовать ${todoRenames.length} ассетов.`);
  process.exit(0);
}

// ---------- бэкап ----------
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const backup = join(homedir(), '.dsh', 'dsh-pet-ru-backup', stamp);
if (!already) {
  for (const f of manifest.files) {
    const dst = join(backup, 'files', f.path);
    mkdirSync(dirname(dst), { recursive: true });
    copyFileSync(join(dir, f.path), dst);
  }
  writeFileSync(
    join(backup, 'backup.json'),
    JSON.stringify({ pluginDir: dir, version: pkg.version, date: stamp, files: manifest.files.map((f) => f.path), renames }, null, 1),
  );
}

// ---------- установка ----------
if (!already) {
  for (const f of manifest.files) {
    copyFileSync(join(here, 'files', f.path), join(dir, f.path));
  }
}
let renamed = 0;
for (const r of todoRenames) {
  renameSync(join(dir, r.from), join(dir, r.to));
  renamed++;
}

// ---------- проверка результата ----------
const bad = manifest.files.filter((f) => sha(join(dir, f.path)) !== f.after).map((f) => f.path);
if (bad.length) fail(`после установки хеши не совпали: ${bad.join(', ')}`);
const missing = renames.filter((r) => !existsSync(join(dir, r.to))).map((r) => r.to);
if (missing.length) fail(`после переименования не хватает: ${missing.slice(0, 5).join(', ')}...`);

console.log(`Готово.
  Папка плагина: ${dir}
  Файлов переведено: ${already ? 'уже были' : manifest.files.length}
  Ассетов переименовано: ${renamed} (уже было: ${alreadyRenamed})
  Бэкап: ${already ? 'не нужен' : backup}

Дальше: перезапустите DSH (или обновите страницу Ctrl+R) — интерфейс будет на русском.${already ? '' : `\nОткат: node install.mjs --restore "${backup}"`}`);
