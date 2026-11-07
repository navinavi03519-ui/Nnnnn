import base64
import html
import mimetypes
from urllib.parse import urljoin, urlparse

import flet as ft
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"}


def main(page: ft.Page):
    page.title = "Asha App - WP Auto Publisher"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = "adaptive"
    page.padding = 16

    scraped = {"paras": [], "headings": [], "images": []}

    # ---------------- Settings (phone me save hoti hain) ----------------
    def load(key, default=""):
        try:
            v = page.client_storage.get(key)
            return v if v is not None else default
        except Exception:
            return default

    def save(key, val):
        try:
            page.client_storage.set(key, val)
        except Exception:
            pass

    s_site = ft.TextField(label="Website URL (e.g. https://yoursite.com)", value=load("site"))
    s_user = ft.TextField(label="WP Username", value=load("user"))
    s_pass = ft.TextField(label="Application Password", value=load("pass"),
                          password=True, can_reveal_password=True)
    s_acf1 = ft.TextField(label="ACF field name for Box 3 (Source URL)", value=load("acf1", "source_url"))
    s_acf2 = ft.TextField(label="ACF field name for Box 4 (Meta Info)", value=load("acf2", "meta_info"))
    s_msg = ft.Text("")

    def site_base():
        u = s_site.value.strip().rstrip("/")
        if u and not u.startswith(("http://", "https://")):
            u = "https://" + u
        return u

    def save_settings(e):
        save("site", site_base())
        save("user", s_user.value.strip())
        save("pass", s_pass.value.strip())
        save("acf1", s_acf1.value.strip())
        save("acf2", s_acf2.value.strip())
        s_site.value = site_base()
        s_msg.value = "✅ Settings save ho gayi!"
        s_msg.color = ft.Colors.GREEN_400
        page.update()

    def auth_headers():
        raw = f"{s_user.value.strip()}:{s_pass.value.strip()}"
        return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}

    def api(path):
        return site_base() + "/wp-json/wp/v2/" + path

    def test_connection(e):
        if not site_base():
            s_msg.value = "❌ Pehle Website URL bharein."
            s_msg.color = ft.Colors.RED_400
            page.update()
            return
        try:
            r = requests.get(api("users/me"), headers=auth_headers(), timeout=15)
            if r.status_code == 200:
                s_msg.value = f"✅ Connected as: {r.json().get('name')}"
                s_msg.color = ft.Colors.GREEN_400
            else:
                s_msg.value = f"❌ Login fail (Code {r.status_code}). Username/App Password check karein."
                s_msg.color = ft.Colors.RED_400
        except Exception as ex:
            s_msg.value = f"❌ Error: {ex}"
            s_msg.color = ft.Colors.RED_400
        page.update()

    # ---------------- Publisher UI ----------------
    url_input = ft.TextField(label="Target Website Link", hint_text="https://example.com/article",
                             border_color=ft.Colors.BLUE_400, expand=True)
    status_text = ft.Text("", weight=ft.FontWeight.BOLD, selectable=True)
    progress = ft.ProgressBar(visible=False)

    box_title = ft.TextField(label="📦 Box 1: Post Title", border_color=ft.Colors.GREEN_400)
    box_content = ft.TextField(label="📦 Box 2: Main Content (Body)", multiline=True,
                               min_lines=4, max_lines=10, border_color=ft.Colors.GREEN_400)
    box_acf_source = ft.TextField(label="📦 Box 3: ACF (Source URL)", border_color=ft.Colors.AMBER_400)
    box_acf_extra = ft.TextField(label="📦 Box 4: ACF (Meta Info)", border_color=ft.Colors.AMBER_400)

    para_count = ft.TextField(label="Kitne paragraphs lene hain?", value="5",
                              keyboard_type=ft.KeyboardType.NUMBER, width=200)
    chk_image = ft.Checkbox(label="Pehli image ko Featured Image banao", value=True)
    chk_extra = ft.Checkbox(label="Bache hue paragraphs bhi content me jodo", value=False)
    status_dd = ft.Dropdown(label="Post Status", value="draft", width=200,
                            options=[ft.dropdown.Option("draft", "Draft"),
                                     ft.dropdown.Option("publish", "Publish"),
                                     ft.dropdown.Option("pending", "Pending Review")])

    def empty_unmapped():
        return ft.Column([
            ft.Text("⚠️ Unmapped / Extra Data Check", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400),
            ft.Text("Abhi tak koi data read nahi hua hai.", color=ft.Colors.GREY_400),
        ])

    unmapped_box = ft.Container(content=empty_unmapped(), padding=15,
                                bgcolor=ft.Colors.GREY_900, border_radius=8)

    def set_status(msg, color):
        status_text.value = msg
        status_text.color = color
        page.update()

    def get_n():
        try:
            return max(1, int(para_count.value))
        except (ValueError, TypeError):
            return 5

    def build_body():
        paras = scraped["paras"]
        n = get_n()
        body = paras[:n] + (paras[n:] if chk_extra.value else [])
        return "\n\n".join(body) if body else "No content found."

    def refresh_unmapped():
        n = get_n()
        left = 0 if chk_extra.value else max(0, len(scraped["paras"]) - n)
        extra = []
        if left:
            extra.append(f"• {left} extra paragraphs reh gaye hain.")
        if scraped["headings"]:
            extra.append(f"• {len(scraped['headings'])} Headings mili hain (Unmapped).")
        if len(scraped["images"]) > 1 or (scraped["images"] and not chk_image.value):
            extra.append(f"• {len(scraped['images'])} Images mili hain (Unmapped).")
        if extra:
            unmapped_box.content = ft.Column([
                ft.Text("⚠️ Yeh Extra Data Kisi Box Mein Mapped Nahi Hai:", weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ORANGE_400),
                *[ft.Text(i, size=13) for i in extra],
                ft.Text("👉 Chahein to 'Bache hue paragraphs' option on karein.", size=12,
                        italic=True, color=ft.Colors.GREY_400),
            ])
        else:
            unmapped_box.content = ft.Column([
                ft.Text("✅ Pura data boxes mein successfully map ho gaya!", color=ft.Colors.GREEN_400,
                        weight=ft.FontWeight.BOLD)])

    def options_changed(e):
        # Agar data fetch ho chuka hai to content box dobara bana do
        if scraped["paras"]:
            box_content.value = build_body()
            refresh_unmapped()
            page.update()

    para_count.on_change = options_changed
    chk_extra.on_change = options_changed
    chk_image.on_change = options_changed

    def fetch_data(e):
        target = url_input.value.strip()
        if target and not target.startswith(("http://", "https://")):
            target = "https://" + target
            url_input.value = target
        if not target:
            set_status("❌ Kripya valid URL dalein!", ft.Colors.RED_400)
            return
        progress.visible = True
        set_status("⏳ Link read kiya ja raha hai...", ft.Colors.BLUE_400)
        try:
            r = requests.get(target, headers=UA, timeout=15)
            if r.status_code != 200:
                progress.visible = False
                set_status(f"❌ URL open nahi hua (Status Code: {r.status_code})", ft.Colors.RED_400)
                return
            soup = BeautifulSoup(r.text, "html.parser")

            og = soup.find("meta", property="og:title")
            if og and og.get("content"):
                title = og["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            else:
                title = "Untitled Post"

            scraped["paras"] = [p.get_text(" ", strip=True) for p in soup.find_all("p")
                                if len(p.get_text(strip=True)) > 30]
            scraped["headings"] = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])
                                   if h.get_text(strip=True)]
            imgs = []
            ogi = soup.find("meta", property="og:image")
            if ogi and ogi.get("content"):
                imgs.append(urljoin(target, ogi["content"]))
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if src and not src.startswith("data:"):
                    full = urljoin(target, src)
                    if full not in imgs:
                        imgs.append(full)
            scraped["images"] = imgs

            box_title.value = title
            box_content.value = build_body()
            box_acf_source.value = target
            box_acf_extra.value = f"Scraped from: {urlparse(target).netloc} | Paragraphs: {len(scraped['paras'])}"
            refresh_unmapped()
            progress.visible = False
            set_status("✅ Data load ho gaya! Check karke Publish karein.", ft.Colors.GREEN_400)
        except Exception as ex:
            progress.visible = False
            set_status(f"❌ Error: {ex}", ft.Colors.RED_400)

    def upload_featured(img_url):
        """Image download karke WP media me upload karta hai, media ID return karta hai."""
        try:
            d = requests.get(img_url, headers=UA, timeout=20)
            if d.status_code != 200:
                return None
            ctype = d.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not ctype.startswith("image/"):
                return None
            ext = mimetypes.guess_extension(ctype) or ".jpg"
            h = auth_headers()
            h["Content-Disposition"] = f'attachment; filename="asha-image{ext}"'
            h["Content-Type"] = ctype
            r = requests.post(api("media"), headers=h, data=d.content, timeout=60)
            if r.status_code in (200, 201):
                return r.json().get("id")
        except Exception:
            pass
        return None

    def publish(e):
        if not (site_base() and s_user.value.strip() and s_pass.value.strip()):
            set_status("❌ Pehle Settings tab me Website/User/App Password bharein.", ft.Colors.RED_400)
            return
        if not box_title.value.strip():
            set_status("❌ Title khali hai. Pehle data fetch karein.", ft.Colors.RED_400)
            return
        progress.visible = True
        set_status("⏳ WordPress par bheja ja raha hai...", ft.Colors.BLUE_400)
        try:
            body_html = "".join(f"<p>{html.escape(line.strip())}</p>"
                                for line in box_content.value.split("\n\n") if line.strip())
            payload = {"title": box_title.value.strip(), "content": body_html, "status": status_dd.value}

            acf = {}
            if s_acf1.value.strip():
                acf[s_acf1.value.strip()] = box_acf_source.value
            if s_acf2.value.strip():
                acf[s_acf2.value.strip()] = box_acf_extra.value
            if acf:
                payload["acf"] = acf

            note = ""
            if chk_image.value and scraped["images"]:
                set_status("⏳ Featured image upload ho rahi hai...", ft.Colors.BLUE_400)
                mid = upload_featured(scraped["images"][0])
                if mid:
                    payload["featured_media"] = mid
                else:
                    note = " (Image upload nahi ho payi)"

            r = requests.post(api("posts"), headers=auth_headers(), json=payload, timeout=60)
            progress.visible = False
            if r.status_code in (200, 201):
                link = r.json().get("link", "")
                set_status(f"🎉 Post ban gayi!{note}\n{link}", ft.Colors.GREEN_400)
            elif r.status_code in (401, 403):
                set_status("❌ Permission/Login error. App Password aur user role check karein.", ft.Colors.RED_400)
            else:
                set_status(f"❌ Fail (Code {r.status_code}): {r.text[:200]}", ft.Colors.RED_400)
        except Exception as ex:
            progress.visible = False
            set_status(f"❌ Error: {ex}", ft.Colors.RED_400)

    def clear_all(e):
        for f in (url_input, box_title, box_content, box_acf_source, box_acf_extra):
            f.value = ""
        scraped.update({"paras": [], "headings": [], "images": []})
        unmapped_box.content = empty_unmapped()
        status_text.value = ""
        page.update()

    publisher_tab = ft.Column([
        ft.Row([url_input]),
        ft.Row([para_count, status_dd], wrap=True),
        chk_image, chk_extra,
        ft.Row([
            ft.ElevatedButton("🔍 Fetch Data", on_click=fetch_data,
                              bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            ft.OutlinedButton("🧹 Clear", on_click=clear_all),
        ], wrap=True),
        progress, status_text,
        box_title, box_content, box_acf_source, box_acf_extra,
        unmapped_box,
        ft.ElevatedButton("🚀 Publish to WordPress", on_click=publish, bgcolor=ft.Colors.GREEN_700,
                          color=ft.Colors.WHITE, height=50),
    ], spacing=12)

    settings_tab = ft.Column([
        ft.Text("WordPress Settings", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("WP Admin → Users → Profile → Application Passwords se password banayein.",
                size=12, color=ft.Colors.GREY_400),
        s_site, s_user, s_pass, s_acf1, s_acf2,
        ft.Row([
            ft.ElevatedButton("💾 Save", on_click=save_settings),
            ft.OutlinedButton("🔌 Test Connection", on_click=test_connection),
        ], wrap=True),
        s_msg,
    ], spacing=12)

    tabs = ft.Tabs(
        selected_index=0, animation_duration=200,
        tabs=[
            ft.Tab(text="Publisher", content=ft.Container(publisher_tab, padding=ft.padding.only(top=16))),
            ft.Tab(text="Settings", content=ft.Container(settings_tab, padding=ft.padding.only(top=16))),
        ])
    page.add(ft.Text("🌸 Asha WP Auto Publisher", size=22, weight=ft.FontWeight.BOLD), tabs)


ft.app(target=main)
