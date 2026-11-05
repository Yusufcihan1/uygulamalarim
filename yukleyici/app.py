"""Uygulama Yükle: bir klasörü sürükle ya da masaüstünde bulunanlardan seç, Uygulamalarım sitesinde yayınla."""
import os
import queue
import re
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image
from tkinterdnd2 import DND_FILES, TkinterDnD

import yayin

BG = "#0f1016"
CARD = "#1b1e2b"
CARD_HI = "#232738"
TEXT = "#e9ebf5"
MUTED = "#8b90a8"
ACCENT = "#7c5cff"
ACCENT_HI = "#9479ff"
CYAN = "#22d3ee"
GREEN = "#34d399"
RED = "#f87171"
FONT = "Segoe UI"


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def mb(n):
    return f"{n / 2**20:,.1f} MB".replace(",", "X").replace(".", ",").replace("X", ".")


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.TkdndVersion = TkinterDnD._require(self)
        ctk.set_appearance_mode("dark")
        self.title("Uygulama Yükle")
        self.geometry("900x660")
        self.minsize(820, 600)
        try:
            self.iconbitmap(resource("icon.ico"))
        except tk.TclError:
            pass

        self.uiq = queue.Queue()
        self.apps = []
        self.pkg = None
        self.icon = None
        self.busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.home = self._build_home()
        self.form = self._build_form()
        self.show(self.home)

        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self._drain()
        self.load()

    def ui(self, fn):
        self.uiq.put(fn)

    def _drain(self):
        while not self.uiq.empty():
            self.uiq.get()()
        self.after(50, self._drain)

    def show(self, page):
        for p in (self.home, self.form):
            p.grid_forget()
        page.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)

    # ------------------------------------------------------------ ana sayfa

    def _build_home(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(3, weight=1)

        head = ctk.CTkFrame(page, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(head, text="Uygulama Yükle", font=(FONT, 26, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkButton(head, text="Siteyi aç ↗", width=110, height=34, corner_radius=17, fg_color=CARD_HI,
                      hover_color="#2d3247", font=(FONT, 13),
                      command=lambda: webbrowser.open(yayin.SITE)).pack(side="right")

        self.drop = ctk.CTkFrame(page, fg_color=CARD, corner_radius=18, border_width=2, border_color=CARD_HI)
        self.drop.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        ctk.CTkLabel(self.drop, text="⬇", font=(FONT, 30), text_color=ACCENT_HI).pack(pady=(20, 0))
        ctk.CTkLabel(self.drop, text="Uygulamanın klasörünü buraya sürükle", font=(FONT, 17, "bold"),
                     text_color=TEXT).pack()
        self.drop_hint = ctk.CTkLabel(
            self.drop, text="Hangi klasör olduğunu bilmen gerekmez: kurulum dosyasını ya da exe'yi kendim bulurum.",
            font=(FONT, 12), text_color=MUTED)
        self.drop_hint.pack(pady=(2, 10))
        ctk.CTkButton(self.drop, text="Klasör seç", width=130, height=36, corner_radius=18, fg_color=ACCENT,
                      hover_color=ACCENT_HI, font=(FONT, 13, "bold"), command=self.pick_folder).pack(pady=(0, 20))

        self.home_status = ctk.CTkLabel(page, text="", font=(FONT, 13), text_color=MUTED, anchor="w")
        self.home_status.grid(row=2, column=0, sticky="w", pady=(10, 4))
        self.list = ctk.CTkScrollableFrame(page, fg_color=CARD, corner_radius=18)
        self.list.grid(row=3, column=0, sticky="nsew")
        self.list.grid_columnconfigure(1, weight=1)
        self.list_msg = ctk.CTkLabel(self.list, text="Aranıyor…", text_color=MUTED, font=(FONT, 13))
        self.list_msg.grid(row=0, column=0, columnspan=4, pady=30)
        return page

    def load(self):
        def work():
            try:
                yayin.ensure_repo()
                apps = [(a, yayin.published_icon(a["id"])) for a in yayin.load_apps()]
                found = [(p, yayin.find_icon(p)) for p in yayin.scan_desktop()]
                self.ui(lambda: self._fill(apps, found))
            except Exception as e:
                msg = str(e)
                self.ui(lambda: self.list_msg.configure(
                    text=f"GitHub'a bağlanılamadı. 'gh auth login' ile giriş yapılmış olmalı.\n\n{msg[:300]}",
                    text_color=RED))
        threading.Thread(target=work, daemon=True).start()

    def _published(self, pkg):
        for a in self.apps:
            if a.get("id") == pkg.id or a.get("name", "").lower() == pkg.name.lower():
                return a
        return None

    def _section(self, row, text):
        ctk.CTkLabel(self.list, text=text, font=(FONT, 15, "bold"), text_color=TEXT, anchor="w").grid(
            row=row, column=0, columnspan=4, sticky="w", padx=14, pady=(14 if row == 0 else 24, 4))

    def _fill(self, apps, found):
        self.apps = [a for a, _ in apps]
        for w in self.list.winfo_children():
            w.destroy()

        row = 0
        self._section(row, "Sitede yayında")
        row += 1
        if not apps:
            ctk.CTkLabel(self.list, text="Henüz yayında uygulama yok.", text_color=MUTED, font=(FONT, 13)).grid(
                row=row, column=0, columnspan=4, sticky="w", padx=14, pady=6)
            row += 1
        for a, icon in sorted(apps, key=lambda t: t[0].get("name", "").lower()):
            ctk.CTkLabel(self.list, image=ctk.CTkImage(icon, size=(40, 40)), text="").grid(
                row=row, column=0, padx=(14, 10), pady=8)
            box = ctk.CTkFrame(self.list, fg_color="transparent")
            box.grid(row=row, column=1, sticky="w")
            ctk.CTkLabel(box, text=a.get("name", a["id"]), font=(FONT, 14, "bold"), text_color=TEXT,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(box, text=f"v{a.get('version', '?')}  ·  {a.get('date', '')}  ·  {mb(a.get('size', 0))}",
                         font=(FONT, 12), text_color=MUTED, anchor="w").pack(anchor="w")
            ctk.CTkButton(self.list, text="Sil", width=100, height=32, corner_radius=16, fg_color=CARD_HI,
                          hover_color="#4a2530", text_color=RED, font=(FONT, 13),
                          command=lambda x=a: self.delete_app(x)).grid(row=row, column=3, padx=(8, 14))
            row += 1

        self._section(row, "Masaüstünde bulunanlar")
        row += 1
        if not found:
            ctk.CTkLabel(self.list, text="Masaüstünde uygulama klasörü bulunamadı. Yukarıdan klasör seçebilirsin.",
                         text_color=MUTED, font=(FONT, 13)).grid(row=row, column=0, columnspan=4, sticky="w",
                                                                 padx=14, pady=6)
            return
        for i, (pkg, icon) in enumerate(found, start=row):
            img = ctk.CTkImage(icon, size=(40, 40))
            ctk.CTkLabel(self.list, image=img, text="").grid(row=i, column=0, padx=(14, 10), pady=8)
            box = ctk.CTkFrame(self.list, fg_color="transparent")
            box.grid(row=i, column=1, sticky="w")
            ctk.CTkLabel(box, text=pkg.name, font=(FONT, 14, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
            ctk.CTkLabel(box, text=f"{os.path.basename(pkg.folder)}  ·  {pkg.kind_label}  ·  {mb(pkg.size)}",
                         font=(FONT, 12), text_color=MUTED, anchor="w").pack(anchor="w")
            pub = self._published(pkg)
            ctk.CTkLabel(self.list, text=f"Yayında v{pub['version']}" if pub else "Yeni",
                         font=(FONT, 12, "bold"), text_color=GREEN if pub else CYAN, width=110).grid(
                row=i, column=2, padx=8)
            ctk.CTkButton(self.list, text="Güncelle" if pub else "Yükle", width=100, height=32, corner_radius=16,
                          fg_color=CARD_HI if pub else ACCENT, hover_color=ACCENT_HI, font=(FONT, 13),
                          command=lambda p=pkg, ic=icon: self.open_form(p, ic)).grid(row=i, column=3, padx=(8, 14))

    def delete_app(self, a):
        if self.busy:
            return
        name = a.get("name", a["id"])
        if not messagebox.askyesno(
                "Uygulamayı sil",
                f"{name} siteden kaldırılsın ve GitHub'daki bütün sürümleri silinsin mi?\n\n"
                "Bu geri alınamaz. Bilgisayarındaki dosyalara dokunulmaz.", icon="warning"):
            return
        self.busy = True

        def log(text):
            self.ui(lambda: self.home_status.configure(text=text, text_color=MUTED))

        def work():
            try:
                n = yayin.unpublish(a["id"], log)
                self.ui(lambda: self.home_status.configure(
                    text=f"✓ {name} silindi ({n} sürüm). Site bir dakika içinde güncellenir.", text_color=GREEN))
            except Exception as e:
                msg = str(e)
                self.ui(lambda: self.home_status.configure(text=f"Silinemedi: {msg[:300]}", text_color=RED))
            finally:
                self.ui(lambda: setattr(self, "busy", False))
                self.load()

        threading.Thread(target=work, daemon=True).start()

    def pick_folder(self):
        path = filedialog.askdirectory(title="Uygulamanın klasörünü seç", initialdir=yayin.DESKTOP)
        if path:
            self.use_path(path)

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if paths:
            self.use_path(paths[0])

    def use_path(self, path):
        pkg = yayin.detect(path)
        if not pkg:
            self.drop_hint.configure(text=f"'{os.path.basename(path)}' içinde exe ya da kurulum dosyası bulunamadı.",
                                     text_color=RED)
            return
        self.drop_hint.configure(text="Hangi klasör olduğunu bilmen gerekmez: kurulum dosyasını ya da exe'yi "
                                      "kendim bulurum.", text_color=MUTED)
        self.open_form(pkg, yayin.find_icon(pkg))

    # ------------------------------------------------------------ yayın formu

    def _build_form(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(page, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(head, text="← Geri", width=80, height=32, corner_radius=16, fg_color=CARD_HI,
                      hover_color="#2d3247", font=(FONT, 13), command=self.back).pack(side="left")
        self.form_title = ctk.CTkLabel(head, text="", font=(FONT, 22, "bold"), text_color=TEXT)
        self.form_title.pack(side="left", padx=14)

        card = ctk.CTkFrame(page, fg_color=CARD, corner_radius=18)
        card.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        card.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, rowspan=8, sticky="n", padx=22, pady=22)
        self.icon_label = ctk.CTkLabel(left, text="")
        self.icon_label.pack()
        ctk.CTkButton(left, text="İkon değiştir", width=110, height=30, corner_radius=15, fg_color=CARD_HI,
                      hover_color="#2d3247", font=(FONT, 12), command=self.pick_icon).pack(pady=(10, 0))

        self.file_info = ctk.CTkLabel(card, text="", font=(FONT, 12), text_color=MUTED, anchor="w", justify="left",
                                      wraplength=560)
        self.file_info.grid(row=0, column=1, sticky="ew", padx=(0, 22), pady=(22, 10))

        def field(row, label):
            ctk.CTkLabel(card, text=label, font=(FONT, 13, "bold"), text_color=TEXT, anchor="w").grid(
                row=row, column=1, sticky="w", padx=(0, 22))

        field(1, "Ad")
        name_row = ctk.CTkFrame(card, fg_color="transparent")
        name_row.grid(row=2, column=1, sticky="ew", padx=(0, 22), pady=(2, 10))
        name_row.grid_columnconfigure(0, weight=1)
        self.e_name = ctk.CTkEntry(name_row, height=36, fg_color=BG, border_color=CARD_HI, font=(FONT, 14))
        self.e_name.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(name_row, text="Sürüm", font=(FONT, 13, "bold"), text_color=TEXT).grid(row=0, column=1,
                                                                                         padx=(14, 8))
        self.e_ver = ctk.CTkEntry(name_row, width=100, height=36, fg_color=BG, border_color=CARD_HI, font=(FONT, 14))
        self.e_ver.grid(row=0, column=2)

        field(3, "Açıklama")
        self.t_desc = ctk.CTkTextbox(card, height=64, fg_color=BG, border_color=CARD_HI, border_width=2,
                                     font=(FONT, 13), wrap="word")
        self.t_desc.grid(row=4, column=1, sticky="ew", padx=(0, 22), pady=(2, 10))
        field(5, "Özellikler (her satıra bir tane, isteğe bağlı)")
        self.t_feat = ctk.CTkTextbox(card, height=96, fg_color=BG, border_color=CARD_HI, border_width=2,
                                     font=(FONT, 13), wrap="word")
        self.t_feat.grid(row=6, column=1, sticky="ew", padx=(0, 22), pady=(2, 22))

        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", pady=18)
        bottom.grid_columnconfigure(1, weight=1)
        self.pub_btn = ctk.CTkButton(bottom, text="Yayınla", width=160, height=46, corner_radius=23,
                                     fg_color=ACCENT, hover_color=ACCENT_HI, font=(FONT, 16, "bold"),
                                     command=self.publish)
        self.pub_btn.grid(row=0, column=0, rowspan=2)
        self.status = ctk.CTkLabel(bottom, text="", font=(FONT, 13), text_color=MUTED, anchor="w", justify="left",
                                   wraplength=560)
        self.status.grid(row=0, column=1, sticky="w", padx=18)
        self.progress = ctk.CTkProgressBar(bottom, height=8, mode="indeterminate", progress_color=CYAN,
                                           fg_color=CARD_HI)
        self.site_btn = ctk.CTkButton(bottom, text="Siteyi aç ↗", width=110, height=34, corner_radius=17,
                                      fg_color=CARD_HI, hover_color="#2d3247", font=(FONT, 13),
                                      command=lambda: webbrowser.open(yayin.SITE))
        return page

    def open_form(self, pkg, icon):
        if self.busy:
            return
        self.pkg, self.icon = pkg, icon
        pub = self._published(pkg)
        self.app_id = pub["id"] if pub else pkg.id
        self.form_title.configure(text=f"{pub['name']} güncelle" if pub else "Yeni uygulama")
        where = pkg.path if pkg.kind == "portable" else os.path.basename(pkg.path)
        self.file_info.configure(text=f"Yüklenecek: {where}\n{pkg.kind_label}  ·  {mb(pkg.size)}"
                                      + (f"\nŞu an yayında: v{pub['version']}" if pub else ""))
        self._set(self.e_name, pub["name"] if pub else pkg.name)
        self._set(self.e_ver, yayin.next_version(pub["version"]) if pub else "1.0.0")
        self._set(self.t_desc, pub.get("description", "") if pub else "")
        self._set(self.t_feat, "\n".join(pub.get("features", [])) if pub else "")
        self._show_icon()
        self.status.configure(text="", text_color=MUTED)
        self.progress.grid_forget()
        self.site_btn.grid_forget()
        self.pub_btn.configure(state="normal", text="Yayınla")
        self.show(self.form)

    @staticmethod
    def _set(widget, text):
        if isinstance(widget, ctk.CTkTextbox):
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
        else:
            widget.delete(0, "end")
            widget.insert(0, text)

    def _show_icon(self):
        self.icon_label.configure(image=ctk.CTkImage(self.icon, size=(96, 96)))

    def pick_icon(self):
        path = filedialog.askopenfilename(title="İkon seç", filetypes=[("Görsel", "*.png *.ico *.jpg *.jpeg")])
        if path:
            try:
                self.icon = yayin.load_icon(path)
                self._show_icon()
            except OSError:
                messagebox.showerror("İkon", "Bu dosya açılamadı.")

    def back(self):
        if not self.busy:
            self.show(self.home)

    def publish(self):
        name = self.e_name.get().strip()
        version = self.e_ver.get().strip().lstrip("vV")
        desc = self.t_desc.get("1.0", "end").strip()
        feats = [f.strip(" -•\t") for f in self.t_feat.get("1.0", "end").splitlines() if f.strip(" -•\t")]
        if not name or not desc:
            self.status.configure(text="Ad ve açıklama gerekli.", text_color=RED)
            return
        if not re.fullmatch(r"\d+(\.\d+){0,3}", version):
            self.status.configure(text="Sürüm 1.0.0 biçiminde olmalı.", text_color=RED)
            return
        pub = next((a for a in self.apps if a.get("id") == self.app_id), None)
        if pub and pub.get("version") == version and not messagebox.askyesno(
                "Aynı sürüm", f"v{version} zaten yayında. Dosyası değiştirilsin mi?"):
            return

        self.busy = True
        self.pub_btn.configure(state="disabled", text="Yayınlanıyor…")
        self.progress.grid(row=1, column=1, sticky="ew", padx=18, pady=(6, 0))
        self.progress.start()

        def log(text):
            self.ui(lambda: self.status.configure(text=text, text_color=MUTED))

        def work():
            try:
                yayin.publish(self.pkg, self.app_id, name, version, desc, feats, self.icon, log)
                self.apps = yayin.load_apps()
                self.ui(lambda: self._done(True, f"✓ {name} v{version} yayınlandı. Site bir dakika içinde güncellenir."))
            except Exception as e:
                msg = str(e)
                self.ui(lambda: self._done(False, f"Yayınlanamadı:\n{msg[:400]}"))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, ok, text):
        self.busy = False
        self.progress.stop()
        self.progress.grid_forget()
        self.status.configure(text=text, text_color=GREEN if ok else RED)
        self.pub_btn.configure(state="normal", text="Yeniden dene" if not ok else "Yayınla")
        if ok:
            self.pub_btn.configure(state="disabled", text="Yayınlandı")
            self.site_btn.grid(row=0, column=2, rowspan=2)
            self.load()


if __name__ == "__main__":
    App().mainloop()
