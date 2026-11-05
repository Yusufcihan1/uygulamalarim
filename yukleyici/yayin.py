"""Uygulamalarım: klasörden yayınlanacak dosyayı bulur, GitHub Releases'e yükler, apps.json'u günceller."""
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageFont

REPO = "Yusufcihan1/uygulamalarim"
SITE = "https://yusufcihan1.github.io/uygulamalarim/"
WORK = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Uygulamalarim", "repo")
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
CREATE_NO_WINDOW = 0x08000000

# Kaynak kod, sanal ortam ve derleme artıkları: yayınlanacak dosya bunların içinde aranmaz.
SKIP_DIRS = {"kaynak", "source", "src", ".venv", "venv", "env", "build", "node_modules", "__pycache__", ".git",
             "_internal", "output", "temp", "tmp", "logs"}
SKIP_EXES = re.compile(r"^(unins\d*|uninstall|crashpad_handler|.*crash.*|python\w*|pip\w*|node|w9xpopen)\.exe$", re.I)
INSTALLER = re.compile(r"(kurulum|setup|install)", re.I)
TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class Package:
    """Bir klasörde bulunan yayınlanabilir uygulama."""

    def __init__(self, kind, path, exe, folder):
        self.kind = kind            # "installer" | "portable" | "exe"
        self.path = path            # yüklenecek dosya; portable için zip'lenecek klasör
        self.exe = exe              # uygulamanın ana exe'si
        self.folder = folder        # kullanıcının seçtiği klasör
        self.name = guess_name(self)
        self.size = folder_size(path) if kind == "portable" else os.path.getsize(path)

    @property
    def kind_label(self):
        return {"installer": "Kurulum dosyası", "portable": "Taşınabilir klasör (zip'lenir)",
                "exe": "Tek exe", "zip": "Zip dosyası"}[self.kind]

    @property
    def id(self):
        return slug(self.name)


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.translate(TR).lower()).strip("-")
    return s or "uygulama"


ZIP_SKIP = {"kaynak", ".venv", "venv", "__pycache__", ".git"}


def folder_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d.lower() not in ZIP_SKIP]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def guess_name(pkg):
    stem = os.path.splitext(os.path.basename(pkg.exe))[0]
    if pkg.kind == "installer":
        stem = INSTALLER.sub("", stem)
    stem = re.sub(r"[-_ ]*v?\d+(\.\d+)+$", "", stem)        # sondaki sürüm numarası
    stem = re.sub(r"[-_]+", " ", stem).strip()
    if len(stem) < 2:
        stem = os.path.basename(os.path.normpath(pkg.folder))
    return stem[:1].upper() + stem[1:]


def _walk_exes(folder, max_depth=2):
    base = os.path.normpath(folder)
    for root, dirs, files in os.walk(base):
        depth = os.path.relpath(root, base).count(os.sep) + (root != base)
        dirs[:] = [] if depth >= max_depth else [d for d in dirs if d.lower() not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(".exe") and not SKIP_EXES.match(f):
                yield depth, os.path.join(root, f)


def detect(path):
    """Seçilen klasörden (ya da dosyadan) yayınlanacak paketi bulur; bulamazsa None."""
    path = os.path.normpath(path)
    if os.path.isfile(path):
        if not path.lower().endswith((".exe", ".msi", ".zip")):
            return None
        folder = os.path.dirname(path)
        if path.lower().endswith(".zip"):
            kind = "zip"  # hazır zip olduğu gibi yüklenir
        elif INSTALLER.search(os.path.basename(path)) or path.lower().endswith(".msi"):
            kind = "installer"
        else:
            kind = "exe"
        return Package(kind, path, path, folder)

    exes = sorted(_walk_exes(path), key=lambda t: (t[0], -os.path.getsize(t[1])))
    if not exes:
        return None
    for _, exe in exes:                                     # 1) kurulum dosyası
        if INSTALLER.search(os.path.basename(exe)):
            return Package("installer", exe, exe, path)
    for _, exe in exes:                                     # 2) yanında _internal/dll olan klasör uygulaması
        d = os.path.dirname(exe)
        if os.path.isdir(os.path.join(d, "_internal")) or any(f.lower().endswith(".dll") for f in os.listdir(d)):
            return Package("portable", d, exe, path)
    return Package("exe", exes[0][1], exes[0][1], path)     # 3) tek başına exe


def scan_desktop():
    """Masaüstündeki klasörlerden yayınlanabilir uygulamaları bulur (yalnız ilk seviye)."""
    found = []
    for name in sorted(os.listdir(DESKTOP), key=str.lower):
        p = os.path.join(DESKTOP, name)
        if not os.path.isdir(p) or name.startswith("."):
            continue
        exes = list(_walk_exes(p, max_depth=1))
        if exes:
            pkg = detect(p)
            if pkg:
                found.append(pkg)
    return found


# ---------------------------------------------------------------- ikon

def find_icon(pkg):
    """Klasördeki icon.png/ico, yoksa exe'nin kendi ikonu, o da yoksa baş harfle üretilmiş ikon."""
    candidates = []
    for root, dirs, files in os.walk(pkg.folder):
        dirs[:] = [d for d in dirs if d.lower() not in {".venv", "venv", "node_modules", ".git", "_internal", "build"}]
        if os.path.relpath(root, pkg.folder).count(os.sep) >= 2:
            dirs[:] = []
        for f in files:
            low = f.lower()
            if low.endswith((".png", ".ico")) and re.search(r"(icon|logo|ikon)", low):
                candidates.append(os.path.join(root, f))
    candidates.sort(key=lambda p: (not p.lower().endswith(".png"), len(p)))
    for c in candidates:
        try:
            return load_icon(c)
        except OSError:
            pass
    try:
        from icoextract import IconExtractor
        data = IconExtractor(pkg.exe).get_icon()
        return load_icon(data)
    except Exception:
        return letter_icon(pkg.name)


def load_icon(src):
    img = Image.open(src)
    if getattr(img, "format", "") == "ICO":
        sizes = img.info.get("sizes") or {img.size}
        img.size = max(sizes)
        img.load()
    return img.convert("RGBA").resize((256, 256), Image.LANCZOS)


def letter_icon(name):
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (s, s))
    a, b = (124, 92, 255), (34, 211, 238)
    grad.putdata([tuple(int(a[i] + (b[i] - a[i]) * (x + y) / (2 * s)) for i in range(3)) + (255,)
                  for y in range(s) for x in range(s)])
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, s - 8, s - 8), radius=58, fill=255)
    img.paste(grad, (0, 0), mask)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 140)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((s / 2, s / 2), (name[:1] or "?").upper(), font=font, fill="white", anchor="mm")
    return img


# ---------------------------------------------------------------- git / gh

def _run(*args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, creationflags=CREATE_NO_WINDOW)
    out = (r.stdout + r.stderr).decode("utf-8", errors="replace").strip()
    if r.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} başarısız:\n{out}")
    return out


def ensure_repo():
    """Yayın için kullanılan yerel kopyayı hazırlar ve günceller."""
    if not os.path.isdir(os.path.join(WORK, ".git")):
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        _run("gh", "repo", "clone", REPO, WORK)
    else:
        _run("git", "pull", "--rebase", "-q", cwd=WORK)


def load_apps():
    try:
        with open(os.path.join(WORK, "apps.json"), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def next_version(version):
    parts = [int(p) for p in re.findall(r"\d+", version or "")][:3] or [1, 0, 0]
    while len(parts) < 3:
        parts.append(0)
    parts[2] += 1
    return ".".join(map(str, parts))


def publish(pkg, app_id, name, version, description, features, icon, log=print):
    """Paketi yükler ve siteyi günceller. Dönüş: indirme bağlantısı."""
    log("Depo güncelleniyor…")
    ensure_repo()
    tag = f"{app_id}-v{version}"
    base = re.sub(r"[^\w\-]+", "-", name.translate(TR)).strip("-")
    tmp = tempfile.mkdtemp(prefix="uygulamalarim-")
    try:
        if pkg.kind == "portable":
            asset = os.path.join(tmp, f"{base}-{version}.zip")
            log("Klasör zip'leniyor…")
            root_name = name.translate(TR)
            with zipfile.ZipFile(asset, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for r, dirs, files in os.walk(pkg.path):
                    dirs[:] = [d for d in dirs if d.lower() not in ZIP_SKIP]
                    for f in files:
                        full = os.path.join(r, f)
                        z.write(full, os.path.join(root_name, os.path.relpath(full, pkg.path)))
        else:
            asset = os.path.join(tmp, f"{base}-{version}{os.path.splitext(pkg.path)[1].lower()}")
            shutil.copy2(pkg.path, asset)
        size = os.path.getsize(asset)
        sha = hashlib.sha256()
        with open(asset, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                sha.update(chunk)

        log(f"GitHub'a yükleniyor ({size / 2**20:.1f} MB)…")
        exists = subprocess.run(["gh", "release", "view", tag, "--repo", REPO], capture_output=True,
                                creationflags=CREATE_NO_WINDOW).returncode == 0
        if exists:
            _run("gh", "release", "upload", tag, asset, "--repo", REPO, "--clobber")
        else:
            _run("gh", "release", "create", tag, asset, "--repo", REPO, "--title", f"{name} {version}",
                 "--notes", description)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    log("Site güncelleniyor…")
    os.makedirs(os.path.join(WORK, "icons"), exist_ok=True)
    icon.save(os.path.join(WORK, "icons", f"{app_id}.png"))
    apps = [a for a in load_apps() if a.get("id") != app_id]
    download = f"https://github.com/{REPO}/releases/download/{tag}/{os.path.basename(asset)}"
    apps.append({
        "id": app_id,
        "name": name,
        "version": version,
        "platform": "Windows",
        "kind": pkg.kind,
        "date": datetime.date.today().isoformat(),
        "description": description,
        "features": features,
        "icon": f"icons/{app_id}.png",
        "size": size,
        "sha256": sha.hexdigest(),
        "download": download,
        "release": f"https://github.com/{REPO}/releases?q={app_id}",
    })
    with open(os.path.join(WORK, "apps.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(apps, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _run("git", "add", "-A", cwd=WORK)
    _run("git", "commit", "-q", "-m", f"{name} {version} yayınlandı", cwd=WORK)
    _run("git", "push", "-q", cwd=WORK)
    return download


def unpublish(app_id, log=print):
    """Uygulamanın bütün sürümlerini GitHub Releases'ten siler ve siteden kaldırır. Geri alınamaz."""
    log("Depo güncelleniyor…")
    ensure_repo()
    apps = load_apps()
    app = next((a for a in apps if a.get("id") == app_id), None)
    releases = json.loads(_run("gh", "release", "list", "--repo", REPO, "--limit", "500", "--json", "tagName"))
    tags = [r["tagName"] for r in releases if r["tagName"].startswith(f"{app_id}-v")]
    for i, tag in enumerate(tags, 1):
        log(f"Sürümler siliniyor ({i}/{len(tags)})…")
        _run("gh", "release", "delete", tag, "--repo", REPO, "--yes", "--cleanup-tag")
    log("Site güncelleniyor…")
    with open(os.path.join(WORK, "apps.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([a for a in apps if a.get("id") != app_id], f, ensure_ascii=False, indent=2)
        f.write("\n")
    icon = os.path.join(WORK, "icons", f"{app_id}.png")
    if os.path.exists(icon):
        os.remove(icon)
    _run("git", "add", "-A", cwd=WORK)
    _run("git", "commit", "-q", "-m", f"{app['name'] if app else app_id} kaldırıldı", cwd=WORK)
    _run("git", "push", "-q", cwd=WORK)
    return len(tags)


def published_icon(app_id):
    try:
        return load_icon(os.path.join(WORK, "icons", f"{app_id}.png"))
    except OSError:
        return letter_icon(app_id)
